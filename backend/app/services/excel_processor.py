import os
import re
import json
import logging
from typing import List, Dict, Tuple, Optional
import pandas as pd
from openpyxl import load_workbook

logger = logging.getLogger(__name__)


class ExcelProcessor:
    """Process Excel files to extract structured equipment data and text chunks"""

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per design spec

    # Common equipment column indicators
    EQUIPMENT_COLUMN_PATTERNS = [
        r'equipment[\s_-]*(tag|id|name)?',
        r'tag[\s_-]*(id|number)?',
        r'device[\s_-]*(tag|id|name)?',
        r'asset[\s_-]*(tag|id|name)?',
        r'component',
        r'item[\s_-]*(number)?',
    ]

    # Common data type indicators
    DATA_TYPE_INDICATORS = {
        'IO_POINT': ['io', 'i/o', 'input', 'output', 'ai', 'ao', 'di', 'do', 'point'],
        'SPECIFICATION': ['spec', 'hp', 'kw', 'voltage', 'amperage', 'manufacturer', 'model'],
        'ALARM': ['alarm', 'fault', 'warning', 'trip', 'alert'],
        'SCHEDULE_ENTRY': ['schedule', 'panel', 'circuit', 'breaker', 'load'],
        'SEQUENCE': ['sequence', 'step', 'operation', 'mode'],
    }

    def _validate_file(self, file_path: str) -> None:
        """Validate file exists and is within size limits"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size} bytes exceeds {self.MAX_FILE_SIZE} limit")

        if file_size == 0:
            raise ValueError(f"File is empty: {file_path}")

    def parse_file(self, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse Excel/CSV file and extract data

        Args:
            file_path: Path to the Excel/CSV file

        Returns:
            Tuple of (structured_data_list, text_chunks_list)
        """
        self._validate_file(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            return self._parse_csv(file_path)
        elif ext in ['.xlsx', '.xls']:
            return self._parse_excel(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _parse_csv(self, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse CSV file"""
        try:
            # Try UTF-8 first
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {file_path}, trying latin-1")
            try:
                df = pd.read_csv(file_path, encoding='latin-1')
            except Exception as e:
                logger.error(f"CSV parsing failed for {file_path}: {e}")
                raise ValueError(f"Unable to parse CSV file: {e}")
        except pd.errors.ParserError as e:
            logger.error(f"CSV format error in {file_path}: {e}")
            raise ValueError(f"Invalid CSV format: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing CSV {file_path}: {e}")
            raise

        return self._process_dataframe(df, "Sheet1", file_path)

    def _parse_excel(self, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse Excel file with multiple sheets"""
        all_structured_data = []
        all_chunks = []

        try:
            xlsx = pd.ExcelFile(file_path)
        except Exception as e:
            logger.error(f"Failed to open Excel file {file_path}: {e}")
            raise ValueError(f"Unable to open Excel file: {e}")

        for sheet_name in xlsx.sheet_names:
            try:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)
                if df.empty:
                    logger.debug(f"Skipping empty sheet: {sheet_name}")
                    continue

                structured_data, chunks = self._process_dataframe(df, sheet_name, file_path)
                all_structured_data.extend(structured_data)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning(f"Error processing sheet {sheet_name}: {e}")
                continue

        return all_structured_data, all_chunks

    def _process_dataframe(self, df: pd.DataFrame, sheet_name: str,
                           file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Process a DataFrame to extract equipment data and chunks"""
        structured_data = []
        chunks = []

        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]

        # Detect schema
        equipment_col, data_type, column_mapping = self._detect_schema(df)

        if equipment_col:
            # Extract structured equipment data
            structured_data = self._extract_structured_data(
                df, equipment_col, data_type, column_mapping, sheet_name
            )

        # Generate text chunks for semantic search
        chunks = self._generate_chunks(df, sheet_name, file_path)

        return structured_data, chunks

    def _detect_schema(self, df: pd.DataFrame) -> Tuple[Optional[str], str, Dict]:
        """Detect the schema of the spreadsheet

        Returns:
            Tuple of (equipment_column_name, data_type, column_mapping)
        """
        equipment_col = None
        data_type = "SCHEDULE_ENTRY"  # Default
        column_mapping = {}

        columns_lower = {col: col.lower() for col in df.columns}

        # Find equipment column
        for col, col_lower in columns_lower.items():
            for pattern in self.EQUIPMENT_COLUMN_PATTERNS:
                if re.search(pattern, col_lower, re.IGNORECASE):
                    equipment_col = col
                    break
            if equipment_col:
                break

        # Detect data type from columns
        type_scores = {dt: 0 for dt in self.DATA_TYPE_INDICATORS}
        for col_lower in columns_lower.values():
            for dt, indicators in self.DATA_TYPE_INDICATORS.items():
                for indicator in indicators:
                    if indicator in col_lower:
                        type_scores[dt] += 1

        if any(type_scores.values()):
            data_type = max(type_scores, key=type_scores.get)

        # Build column mapping
        for col, col_lower in columns_lower.items():
            if 'description' in col_lower or 'desc' in col_lower:
                column_mapping['description'] = col
            elif 'type' in col_lower:
                column_mapping['type'] = col
            elif 'value' in col_lower or 'setpoint' in col_lower:
                column_mapping['value'] = col
            elif 'unit' in col_lower:
                column_mapping['unit'] = col
            elif 'category' in col_lower or 'priority' in col_lower:
                column_mapping['category'] = col

        return equipment_col, data_type, column_mapping

    def _extract_structured_data(self, df: pd.DataFrame, equipment_col: str,
                                 data_type: str, column_mapping: Dict,
                                 sheet_name: str) -> List[Dict]:
        """Extract structured equipment data from DataFrame"""
        structured_data = []

        for idx, row in df.iterrows():
            equipment_tag = row.get(equipment_col)

            # Skip rows without equipment tag
            if pd.isna(equipment_tag) or str(equipment_tag).strip() == '':
                continue

            equipment_tag = str(equipment_tag).strip()

            # Build data JSON from row
            row_data = {}
            for key, col in column_mapping.items():
                value = row.get(col)
                if not pd.isna(value):
                    row_data[key] = str(value)

            # Add all non-mapped columns as extra data
            for col in df.columns:
                if col not in [equipment_col] + list(column_mapping.values()):
                    value = row.get(col)
                    if not pd.isna(value):
                        row_data[col] = str(value)

            structured_data.append({
                'equipment_tag': equipment_tag,
                'data_type': data_type,
                'data_json': json.dumps(row_data, default=str),
                'source_location': f"{sheet_name}:Row {idx + 2}"  # +2 for 1-indexed + header
            })

        return structured_data

    def _generate_chunks(self, df: pd.DataFrame, sheet_name: str,
                         file_path: str, chunk_size: int = 10) -> List[Dict]:
        """Generate text chunks for semantic search

        Args:
            df: DataFrame to chunk
            sheet_name: Name of the sheet
            file_path: Source file path
            chunk_size: Number of rows per chunk
        """
        chunks = []

        if df.empty:
            return chunks

        # Generate header description
        header_text = f"Columns: {', '.join(df.columns)}\n"

        # Chunk rows
        for start_idx in range(0, len(df), chunk_size):
            end_idx = min(start_idx + chunk_size, len(df))
            chunk_df = df.iloc[start_idx:end_idx]

            # Convert chunk to readable text
            rows_text = []
            for idx, row in chunk_df.iterrows():
                row_parts = []
                for col in df.columns:
                    value = row[col]
                    if not pd.isna(value):
                        row_parts.append(f"{col}: {value}")
                if row_parts:
                    rows_text.append("; ".join(row_parts))

            content = header_text + "\n".join(rows_text)

            # Extract equipment tags from this chunk
            equipment_tags = self._extract_equipment_tags(chunk_df)

            chunks.append({
                'chunk_index': len(chunks),
                'content': content,
                'source_location': f"{sheet_name}:Rows {start_idx + 2}-{end_idx + 1}",
                'equipment_tags': json.dumps(equipment_tags, default=str) if equipment_tags else None
            })

        return chunks

    def _extract_equipment_tags(self, df: pd.DataFrame) -> List[str]:
        """Extract equipment tags from a DataFrame chunk"""
        tags = set()

        # Pattern for equipment tags (e.g., RTU-F04, VFD-101, AHU_01)
        tag_pattern = r'\b[A-Z]{2,4}[-_\s]?[A-Z]?\d{1,4}[A-Z]?\b'

        for col in df.columns:
            for value in df[col].dropna().astype(str):
                matches = re.findall(tag_pattern, value, re.IGNORECASE)
                tags.update(match.upper() for match in matches)

        return list(tags)


# Singleton instance
excel_processor = ExcelProcessor()
