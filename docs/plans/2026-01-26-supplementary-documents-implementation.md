# Supplementary Documents Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Excel and Word document uploads to enhance RAG answers with IO lists, equipment schedules, sequences of operation, and other project documentation.

**Architecture:** Hybrid storage with structured data (equipment_data table) for Excel rows and text chunks with embeddings (supplementary_chunks) for semantic search. Fuzzy matching links equipment tags across documents. Multi-source RAG searches PDFs, supplementary chunks, and structured data in parallel.

**Tech Stack:** Python (openpyxl, python-docx, fuzzywuzzy), FastAPI, PostgreSQL with pgvector, Vue 3, TypeScript

---

## Phase 1: Foundation

### Task 1: Add Python Dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add new dependencies**

Add these lines to `backend/requirements.txt`:

```
# Supplementary document processing
openpyxl>=3.1.0
python-docx>=1.1.0
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.25.0
```

**Step 2: Rebuild backend container**

Run: `docker-compose build backend`
Expected: Build succeeds with new packages installed

**Step 3: Verify installation**

Run: `docker-compose run --rm backend python -c "import openpyxl; import docx; from fuzzywuzzy import fuzz; print('OK')"`
Expected: Prints "OK"

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add openpyxl, python-docx, fuzzywuzzy for supplementary docs"
```

---

### Task 2: Create Database Migration

**Files:**
- Create: `scripts/migrations/002_supplementary_documents.sql`

**Step 1: Write migration SQL**

Create `scripts/migrations/002_supplementary_documents.sql`:

```sql
-- Supplementary Documents: Excel/Word files with project documentation
CREATE TABLE IF NOT EXISTS supplementary_documents (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    document_type VARCHAR(20) NOT NULL,  -- EXCEL, WORD
    content_category VARCHAR(50),  -- IO_LIST, EQUIPMENT_SCHEDULE, SEQUENCE_OF_OPERATION, COMMISSIONING, SUBMITTAL, OTHER
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    processed INTEGER DEFAULT 0,  -- 0=pending, 1=processing, 2=done, -1=error
    processing_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_supp_doc_project ON supplementary_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_supp_doc_type ON supplementary_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_supp_doc_category ON supplementary_documents(content_category);

-- Supplementary Chunks: Text chunks from Word docs and Excel sheets for semantic search
CREATE TABLE IF NOT EXISTS supplementary_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES supplementary_documents(id) ON DELETE CASCADE NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT,
    source_location VARCHAR(200),  -- "Sheet1:A1-F20" or "Section 3.2"
    equipment_tags TEXT,  -- JSON array of tags found in chunk
    embedding vector(384)
);

CREATE INDEX IF NOT EXISTS idx_supp_chunk_doc ON supplementary_chunks(document_id);

-- Equipment Data: Structured data extracted from Excel (IO points, specs, alarms)
CREATE TABLE IF NOT EXISTS equipment_data (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES supplementary_documents(id) ON DELETE CASCADE NOT NULL,
    equipment_tag VARCHAR(100) NOT NULL,
    equipment_id INTEGER REFERENCES equipment(id) ON DELETE SET NULL,
    match_confidence FLOAT,
    data_type VARCHAR(50) NOT NULL,  -- IO_POINT, SPECIFICATION, ALARM, SCHEDULE_ENTRY, SEQUENCE
    data_json TEXT NOT NULL,
    source_location VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_equip_data_doc ON equipment_data(document_id);
CREATE INDEX IF NOT EXISTS idx_equip_data_tag ON equipment_data(equipment_tag);
CREATE INDEX IF NOT EXISTS idx_equip_data_equipment ON equipment_data(equipment_id);
CREATE INDEX IF NOT EXISTS idx_equip_data_type ON equipment_data(data_type);

-- Equipment Aliases: Alternate names for equipment found across documents
CREATE TABLE IF NOT EXISTS equipment_aliases (
    id SERIAL PRIMARY KEY,
    equipment_id INTEGER REFERENCES equipment(id) ON DELETE CASCADE NOT NULL,
    alias VARCHAR(100) NOT NULL,
    source VARCHAR(255),
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(equipment_id, alias)
);

CREATE INDEX IF NOT EXISTS idx_equip_alias_equipment ON equipment_aliases(equipment_id);
CREATE INDEX IF NOT EXISTS idx_equip_alias_alias ON equipment_aliases(alias);

-- Equipment Profiles: Pre-computed aggregated data from all sources
CREATE TABLE IF NOT EXISTS equipment_profiles (
    id SERIAL PRIMARY KEY,
    equipment_id INTEGER REFERENCES equipment(id) ON DELETE CASCADE NOT NULL UNIQUE,
    profile_json TEXT NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_equip_profile_equipment ON equipment_profiles(equipment_id);
```

**Step 2: Run migration**

Run: `docker-compose exec db psql -U postgres -d electric_rag -f /docker-entrypoint-initdb.d/002_supplementary_documents.sql`

Note: You may need to copy the file first:
```bash
docker cp scripts/migrations/002_supplementary_documents.sql electric_rag-db-1:/docker-entrypoint-initdb.d/
docker-compose exec db psql -U postgres -d electric_rag -f /docker-entrypoint-initdb.d/002_supplementary_documents.sql
```

Expected: Tables created successfully

**Step 3: Verify tables exist**

Run: `docker-compose exec db psql -U postgres -d electric_rag -c "\dt supplementary*"`
Expected: Shows supplementary_documents, supplementary_chunks tables

**Step 4: Commit**

```bash
git add scripts/migrations/002_supplementary_documents.sql
git commit -m "db: add supplementary documents tables migration"
```

---

### Task 3: Add Database Models

**Files:**
- Modify: `backend/app/models/database.py`

**Step 1: Add SupplementaryDocument model**

Add after the `Document` class in `backend/app/models/database.py`:

```python
class SupplementaryDocument(Base):
    """Represents a supplementary document (Excel/Word) with project documentation"""
    __tablename__ = "supplementary_documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    document_type = Column(String(20), nullable=False)  # EXCEL, WORD
    content_category = Column(String(50))  # IO_LIST, EQUIPMENT_SCHEDULE, etc.
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    processed = Column(Integer, default=0)
    processing_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="supplementary_documents")
    chunks = relationship("SupplementaryChunk", back_populates="document", cascade="all, delete-orphan")
    equipment_data = relationship("EquipmentData", back_populates="document", cascade="all, delete-orphan")


class SupplementaryChunk(Base):
    """Text chunks from supplementary documents for semantic search"""
    __tablename__ = "supplementary_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("supplementary_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text)
    source_location = Column(String(200))
    equipment_tags = Column(Text)  # JSON array
    embedding = Column(Vector(384))

    document = relationship("SupplementaryDocument", back_populates="chunks")


class EquipmentData(Base):
    """Structured data extracted from supplementary documents"""
    __tablename__ = "equipment_data"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("supplementary_documents.id", ondelete="CASCADE"), nullable=False)
    equipment_tag = Column(String(100), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="SET NULL"))
    match_confidence = Column(Float)
    data_type = Column(String(50), nullable=False)  # IO_POINT, SPECIFICATION, ALARM, etc.
    data_json = Column(Text, nullable=False)
    source_location = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("SupplementaryDocument", back_populates="equipment_data")
    equipment = relationship("Equipment", back_populates="data_entries")


class EquipmentAlias(Base):
    """Alternate names for equipment found across documents"""
    __tablename__ = "equipment_aliases"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(100), nullable=False)
    source = Column(String(255))
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="aliases")

    __table_args__ = (
        Index('idx_alias_unique', 'equipment_id', 'alias', unique=True),
    )


class EquipmentProfile(Base):
    """Pre-computed aggregated equipment data from all sources"""
    __tablename__ = "equipment_profiles"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, unique=True)
    profile_json = Column(Text, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="profile")
```

**Step 2: Update Equipment model relationships**

Add these relationships to the `Equipment` class:

```python
    # Add to Equipment class
    data_entries = relationship("EquipmentData", back_populates="equipment")
    aliases = relationship("EquipmentAlias", back_populates="equipment", cascade="all, delete-orphan")
    profile = relationship("EquipmentProfile", back_populates="equipment", uselist=False, cascade="all, delete-orphan")
```

**Step 3: Update Project model relationships**

Add this relationship to the `Project` class:

```python
    # Add to Project class
    supplementary_documents = relationship("SupplementaryDocument", back_populates="project", cascade="all, delete-orphan")
```

**Step 4: Verify models load**

Run: `docker-compose exec backend python -c "from app.models.database import SupplementaryDocument, EquipmentData; print('OK')"`
Expected: Prints "OK"

**Step 5: Commit**

```bash
git add backend/app/models/database.py
git commit -m "models: add supplementary document database models"
```

---

### Task 4: Add Pydantic Schemas

**Files:**
- Modify: `backend/app/models/schemas.py`

**Step 1: Add supplementary document schemas**

Add these schemas to `backend/app/models/schemas.py`:

```python
class SupplementaryDocumentBase(BaseModel):
    original_filename: str
    document_type: str
    content_category: Optional[str] = None


class SupplementaryDocumentCreate(SupplementaryDocumentBase):
    pass


class SupplementaryDocumentResponse(SupplementaryDocumentBase):
    id: int
    project_id: Optional[int]
    filename: str
    file_path: str
    file_size: Optional[int]
    processed: int
    processing_error: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SupplementaryChunkResponse(BaseModel):
    id: int
    chunk_index: int
    content: Optional[str]
    source_location: Optional[str]
    equipment_tags: Optional[str]

    class Config:
        from_attributes = True


class EquipmentDataResponse(BaseModel):
    id: int
    equipment_tag: str
    equipment_id: Optional[int]
    match_confidence: Optional[float]
    data_type: str
    data_json: str
    source_location: Optional[str]

    class Config:
        from_attributes = True


class SupplementaryDocumentDetail(SupplementaryDocumentResponse):
    chunks: List[SupplementaryChunkResponse] = []
    equipment_data: List[EquipmentDataResponse] = []


class EquipmentAliasResponse(BaseModel):
    id: int
    alias: str
    source: Optional[str]
    confidence: float

    class Config:
        from_attributes = True


class EquipmentProfileResponse(BaseModel):
    equipment_id: int
    profile_json: str
    last_updated: datetime

    class Config:
        from_attributes = True


class SupplementaryUploadResponse(BaseModel):
    document_id: int
    filename: str
    document_type: str
    message: str
```

**Step 2: Verify schemas**

Run: `docker-compose exec backend python -c "from app.models.schemas import SupplementaryDocumentResponse; print('OK')"`
Expected: Prints "OK"

**Step 3: Commit**

```bash
git add backend/app/models/schemas.py
git commit -m "schemas: add supplementary document pydantic schemas"
```

---

### Task 5: Create Alias Service

**Files:**
- Create: `backend/app/services/alias_service.py`

**Step 1: Create alias service**

Create `backend/app/services/alias_service.py`:

```python
import re
import logging
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from fuzzywuzzy import fuzz

from app.models.database import Equipment, EquipmentAlias

logger = logging.getLogger(__name__)


class AliasService:
    """Handles equipment tag fuzzy matching and alias management"""

    def normalize_tag(self, tag: str) -> str:
        """Normalize tag for comparison: RTU-F04 → rtuf04"""
        if not tag:
            return ""
        return re.sub(r'[-_\s]', '', tag.lower())

    def fuzzy_match(
        self,
        db: Session,
        tag: str,
        project_id: int,
        threshold: int = 85
    ) -> Tuple[Optional[int], float]:
        """
        Find best matching equipment for a tag.

        Returns:
            Tuple of (equipment_id, confidence) where confidence is 0-1.
            equipment_id is None if no match above threshold.
        """
        normalized = self.normalize_tag(tag)
        if not normalized:
            return (None, 0.0)

        # Get all equipment in project
        equipment_list = db.query(Equipment).filter(
            Equipment.project_id == project_id
        ).all()

        best_match = None
        best_score = 0

        for eq in equipment_list:
            # Compare normalized tag
            score = fuzz.ratio(normalized, self.normalize_tag(eq.tag))

            # Also check existing aliases
            aliases = db.query(EquipmentAlias).filter(
                EquipmentAlias.equipment_id == eq.id
            ).all()

            for alias in aliases:
                alias_score = fuzz.ratio(normalized, self.normalize_tag(alias.alias))
                score = max(score, alias_score)

            if score > best_score:
                best_score = score
                best_match = eq

        # Return match if above threshold
        if best_score >= threshold:
            return (best_match.id, best_score / 100.0)

        return (None, best_score / 100.0)

    def add_alias(
        self,
        db: Session,
        equipment_id: int,
        alias: str,
        source: str,
        confidence: float = 1.0
    ) -> Optional[EquipmentAlias]:
        """Add an alias for equipment if it doesn't exist"""
        # Check if alias already exists
        existing = db.query(EquipmentAlias).filter(
            EquipmentAlias.equipment_id == equipment_id,
            func.lower(EquipmentAlias.alias) == alias.lower()
        ).first()

        if existing:
            return existing

        alias_record = EquipmentAlias(
            equipment_id=equipment_id,
            alias=alias,
            source=source,
            confidence=confidence
        )
        db.add(alias_record)
        db.flush()
        return alias_record

    def get_equipment_by_tag_or_alias(
        self,
        db: Session,
        tag: str,
        project_id: int
    ) -> Optional[Equipment]:
        """Find equipment by exact tag match or alias"""
        # Try exact tag match first
        equipment = db.query(Equipment).filter(
            func.upper(Equipment.tag) == tag.upper(),
            Equipment.project_id == project_id
        ).first()

        if equipment:
            return equipment

        # Try alias match
        alias = db.query(EquipmentAlias).join(Equipment).filter(
            func.upper(EquipmentAlias.alias) == tag.upper(),
            Equipment.project_id == project_id
        ).first()

        if alias:
            return alias.equipment

        return None

    def get_all_tags_and_aliases(
        self,
        db: Session,
        project_id: int
    ) -> List[Tuple[str, int]]:
        """Get all equipment tags and aliases for a project.

        Returns:
            List of (tag_or_alias, equipment_id) tuples
        """
        results = []

        # Get all equipment tags
        equipment_list = db.query(Equipment).filter(
            Equipment.project_id == project_id
        ).all()

        for eq in equipment_list:
            results.append((eq.tag, eq.id))

            # Get aliases
            aliases = db.query(EquipmentAlias).filter(
                EquipmentAlias.equipment_id == eq.id
            ).all()

            for alias in aliases:
                results.append((alias.alias, eq.id))

        return results


alias_service = AliasService()
```

**Step 2: Verify service**

Run: `docker-compose exec backend python -c "from app.services.alias_service import alias_service; print('OK')"`
Expected: Prints "OK"

**Step 3: Commit**

```bash
git add backend/app/services/alias_service.py
git commit -m "feat: add alias service for fuzzy equipment matching"
```

---

### Task 6: Create Excel Processor

**Files:**
- Create: `backend/app/services/excel_processor.py`

**Step 1: Create Excel processor service**

Create `backend/app/services/excel_processor.py`:

```python
import json
import logging
import os
from typing import List, Dict, Any, Optional
from openpyxl import load_workbook
import pandas as pd

logger = logging.getLogger(__name__)


class ExcelProcessor:
    """Processes Excel files to extract structured data and text chunks"""

    # Common equipment tag patterns
    EQUIPMENT_PATTERNS = [
        r'\b(RTU[-_\s]?[A-Z]?\d+)\b',
        r'\b(AHU[-_\s]?\d+[A-Z]?)\b',
        r'\b(VFD[-_\s]?\d+)\b',
        r'\b(FCU[-_\s]?\d+)\b',
        r'\b(VAV[-_\s]?\d+)\b',
        r'\b(EF[-_\s]?\d+)\b',
        r'\b(SF[-_\s]?\d+)\b',
        r'\b(CHW[-_\s]?P[-_\s]?\d+)\b',
        r'\b(HWP[-_\s]?\d+)\b',
        r'\b(CT[-_\s]?\d+)\b',
        r'\b(CH[-_\s]?\d+)\b',
        r'\b(B[-_\s]?\d+)\b',
        r'\b(P[-_\s]?\d+)\b',
        r'\b(MCC[-_\s]?\d+)\b',
        r'\b(PNL[-_\s]?\d+)\b',
        r'\b(CP[-_\s]?\d+)\b',
    ]

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process an Excel file.

        Returns:
            {
                "sheets": [
                    {
                        "name": "Sheet1",
                        "rows": [...],
                        "schema": {...},
                        "text_content": "..."
                    }
                ],
                "detected_category": "IO_LIST" | "EQUIPMENT_SCHEDULE" | ...
            }
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            return self._process_csv(file_path)
        else:
            return self._process_excel(file_path)

    def _process_excel(self, file_path: str) -> Dict[str, Any]:
        """Process .xlsx/.xls file"""
        wb = load_workbook(file_path, data_only=True)
        result = {"sheets": [], "detected_category": None}

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            sheet_data = self._process_sheet(sheet, sheet_name)
            if sheet_data["rows"]:  # Only include non-empty sheets
                result["sheets"].append(sheet_data)

        # Detect overall category based on content
        result["detected_category"] = self._detect_category(result["sheets"])

        return result

    def _process_csv(self, file_path: str) -> Dict[str, Any]:
        """Process CSV file"""
        df = pd.read_csv(file_path)

        rows = df.to_dict('records')
        headers = list(df.columns)

        sheet_data = {
            "name": "Sheet1",
            "headers": headers,
            "rows": rows,
            "schema": self._detect_schema(headers, rows[:5] if rows else []),
            "text_content": self._rows_to_text(headers, rows)
        }

        category = self._detect_category([sheet_data])

        return {
            "sheets": [sheet_data],
            "detected_category": category
        }

    def _process_sheet(self, sheet, sheet_name: str) -> Dict[str, Any]:
        """Process a single worksheet"""
        # Read all data
        data = []
        for row in sheet.iter_rows(values_only=True):
            # Skip completely empty rows
            if any(cell is not None for cell in row):
                data.append(list(row))

        if not data:
            return {"name": sheet_name, "rows": [], "headers": [], "schema": {}, "text_content": ""}

        # Find header row (first row with mostly text)
        header_idx = self._find_header_row(data)
        headers = [str(h) if h else f"Column{i}" for i, h in enumerate(data[header_idx])] if header_idx < len(data) else []

        # Convert to list of dicts
        rows = []
        for row_data in data[header_idx + 1:]:
            row_dict = {}
            for i, val in enumerate(row_data):
                if i < len(headers):
                    row_dict[headers[i]] = val
            if any(v is not None for v in row_dict.values()):
                rows.append(row_dict)

        schema = self._detect_schema(headers, rows[:5] if rows else [])
        text_content = self._rows_to_text(headers, rows)

        return {
            "name": sheet_name,
            "headers": headers,
            "rows": rows,
            "schema": schema,
            "text_content": text_content
        }

    def _find_header_row(self, data: List[List]) -> int:
        """Find the row that looks most like a header"""
        for i, row in enumerate(data[:10]):  # Check first 10 rows
            # Header rows typically have mostly strings
            non_empty = [c for c in row if c is not None]
            if non_empty:
                string_count = sum(1 for c in non_empty if isinstance(c, str))
                if string_count / len(non_empty) > 0.7:
                    return i
        return 0

    def _detect_schema(self, headers: List[str], sample_rows: List[Dict]) -> Dict[str, Any]:
        """Detect schema from headers and sample data"""
        schema = {
            "equipment_column": None,
            "data_type": "UNKNOWN",
            "column_mapping": {}
        }

        headers_lower = [h.lower() if h else "" for h in headers]

        # Detect equipment tag column
        equipment_keywords = ['unit', 'tag', 'equipment', 'device', 'name', 'id']
        for i, h in enumerate(headers_lower):
            if any(kw in h for kw in equipment_keywords):
                schema["equipment_column"] = i
                break

        # Detect data type and map columns
        io_keywords = ['point', 'io', 'input', 'output', 'signal', 'type', 'ai', 'ao', 'di', 'do']
        schedule_keywords = ['hp', 'voltage', 'amp', 'kw', 'manufacturer', 'model', 'size']
        alarm_keywords = ['alarm', 'setpoint', 'limit', 'threshold', 'priority', 'category']

        io_score = sum(1 for h in headers_lower if any(kw in h for kw in io_keywords))
        schedule_score = sum(1 for h in headers_lower if any(kw in h for kw in schedule_keywords))
        alarm_score = sum(1 for h in headers_lower if any(kw in h for kw in alarm_keywords))

        if io_score >= 2:
            schema["data_type"] = "IO_LIST"
        elif schedule_score >= 2:
            schema["data_type"] = "EQUIPMENT_SCHEDULE"
        elif alarm_score >= 2:
            schema["data_type"] = "ALARM"

        # Map known columns
        for i, h in enumerate(headers_lower):
            if 'point' in h and 'name' in h:
                schema["column_mapping"]["point_name"] = i
            elif h in ['type', 'io type', 'io_type']:
                schema["column_mapping"]["io_type"] = i
            elif 'description' in h or 'desc' in h:
                schema["column_mapping"]["description"] = i
            elif 'alarm' in h:
                schema["column_mapping"]["alarm_category"] = i
            elif 'setpoint' in h or 'set point' in h:
                schema["column_mapping"]["setpoint"] = i
            elif 'hp' in h or 'horsepower' in h:
                schema["column_mapping"]["hp"] = i
            elif 'voltage' in h or 'volt' in h:
                schema["column_mapping"]["voltage"] = i
            elif 'manufacturer' in h or 'mfr' in h:
                schema["column_mapping"]["manufacturer"] = i
            elif 'model' in h:
                schema["column_mapping"]["model"] = i

        return schema

    def _detect_category(self, sheets: List[Dict]) -> str:
        """Detect overall document category"""
        data_types = [s.get("schema", {}).get("data_type") for s in sheets]

        if "IO_LIST" in data_types:
            return "IO_LIST"
        elif "EQUIPMENT_SCHEDULE" in data_types:
            return "EQUIPMENT_SCHEDULE"
        elif "ALARM" in data_types:
            return "IO_LIST"  # Alarm lists are typically part of IO lists

        return "OTHER"

    def _rows_to_text(self, headers: List[str], rows: List[Dict]) -> str:
        """Convert rows to searchable text"""
        lines = []

        # Add header context
        if headers:
            lines.append("Columns: " + ", ".join(str(h) for h in headers if h))

        # Add row content
        for row in rows:
            row_parts = []
            for k, v in row.items():
                if v is not None and str(v).strip():
                    row_parts.append(f"{k}: {v}")
            if row_parts:
                lines.append(" | ".join(row_parts))

        return "\n".join(lines)

    def extract_equipment_from_row(self, row: Dict, schema: Dict) -> Optional[str]:
        """Extract equipment tag from a row based on schema"""
        eq_col = schema.get("equipment_column")
        if eq_col is not None:
            headers = list(row.keys())
            if eq_col < len(headers):
                val = row.get(headers[eq_col])
                if val:
                    return str(val).strip()

        # Fallback: look for equipment pattern in any column
        import re
        for val in row.values():
            if val:
                for pattern in self.EQUIPMENT_PATTERNS:
                    match = re.search(pattern, str(val), re.IGNORECASE)
                    if match:
                        return match.group(1)

        return None


excel_processor = ExcelProcessor()
```

**Step 2: Verify processor**

Run: `docker-compose exec backend python -c "from app.services.excel_processor import excel_processor; print('OK')"`
Expected: Prints "OK"

**Step 3: Commit**

```bash
git add backend/app/services/excel_processor.py
git commit -m "feat: add Excel processor for parsing spreadsheets"
```

---

### Task 7: Create Word Processor

**Files:**
- Create: `backend/app/services/word_processor.py`

**Step 1: Create Word processor service**

Create `backend/app/services/word_processor.py`:

```python
import re
import logging
from typing import List, Dict, Any, Optional
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

logger = logging.getLogger(__name__)


class WordProcessor:
    """Processes Word documents to extract text chunks with section hierarchy"""

    # Target chunk size in characters (roughly 500 tokens)
    TARGET_CHUNK_SIZE = 2000
    CHUNK_OVERLAP = 200

    # Equipment tag patterns
    EQUIPMENT_PATTERNS = [
        r'\b(RTU[-_\s]?[A-Z]?\d+)\b',
        r'\b(AHU[-_\s]?\d+[A-Z]?)\b',
        r'\b(VFD[-_\s]?\d+)\b',
        r'\b(FCU[-_\s]?\d+)\b',
        r'\b(VAV[-_\s]?\d+)\b',
        r'\b(EF[-_\s]?\d+)\b',
        r'\b(SF[-_\s]?\d+)\b',
        r'\b(CHW[-_\s]?P[-_\s]?\d+)\b',
        r'\b(HWP[-_\s]?\d+)\b',
        r'\b(CT[-_\s]?\d+)\b',
        r'\b(CH[-_\s]?\d+)\b',
        r'\b(MCC[-_\s]?\d+)\b',
        r'\b(PNL[-_\s]?\d+)\b',
        r'\b(CP[-_\s]?\d+)\b',
    ]

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process a Word document.

        Returns:
            {
                "chunks": [
                    {
                        "content": "...",
                        "heading_path": "1.0 General > 1.2 Overview",
                        "equipment_tags": ["RTU-F04", "AHU-1"]
                    }
                ],
                "detected_category": "SEQUENCE_OF_OPERATION" | ...
            }
        """
        try:
            doc = Document(file_path)
        except PackageNotFoundError:
            logger.error(f"Cannot open document: {file_path}")
            return {"chunks": [], "detected_category": "OTHER", "error": "Cannot open document"}

        # Extract content with structure
        sections = self._extract_sections(doc)

        # Create chunks
        chunks = self._create_chunks(sections)

        # Detect category
        category = self._detect_category(chunks)

        return {
            "chunks": chunks,
            "detected_category": category
        }

    def _extract_sections(self, doc: Document) -> List[Dict[str, Any]]:
        """Extract document content organized by sections"""
        sections = []
        current_headings = []  # Stack of heading levels
        current_content = []

        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            text = para.text.strip()

            if not text:
                continue

            # Check if this is a heading
            if style_name.startswith('Heading'):
                # Save current section
                if current_content:
                    sections.append({
                        "heading_path": " > ".join(current_headings) if current_headings else "Document",
                        "content": "\n".join(current_content)
                    })
                    current_content = []

                # Update heading stack
                try:
                    level = int(style_name.replace('Heading ', '').replace('Heading', '1'))
                except ValueError:
                    level = 1

                # Pop headings of same or lower level
                while current_headings and len(current_headings) >= level:
                    current_headings.pop()

                current_headings.append(text)
            else:
                current_content.append(text)

        # Save final section
        if current_content:
            sections.append({
                "heading_path": " > ".join(current_headings) if current_headings else "Document",
                "content": "\n".join(current_content)
            })

        # Also extract tables
        for table in doc.tables:
            table_text = self._table_to_text(table)
            if table_text:
                sections.append({
                    "heading_path": "Table",
                    "content": table_text
                })

        return sections

    def _table_to_text(self, table) -> str:
        """Convert table to text representation"""
        lines = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
        return "\n".join(lines)

    def _create_chunks(self, sections: List[Dict]) -> List[Dict[str, Any]]:
        """Create appropriately sized chunks from sections"""
        chunks = []

        for section in sections:
            content = section["content"]
            heading_path = section["heading_path"]

            # If section is small enough, keep as one chunk
            if len(content) <= self.TARGET_CHUNK_SIZE:
                equipment_tags = self._extract_equipment_tags(content)
                chunks.append({
                    "content": content,
                    "heading_path": heading_path,
                    "equipment_tags": equipment_tags
                })
            else:
                # Split large sections into chunks with overlap
                section_chunks = self._split_content(content, heading_path)
                chunks.extend(section_chunks)

        return chunks

    def _split_content(self, content: str, heading_path: str) -> List[Dict[str, Any]]:
        """Split content into overlapping chunks"""
        chunks = []

        # Split by paragraphs first
        paragraphs = content.split('\n')

        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            if current_size + para_size > self.TARGET_CHUNK_SIZE and current_chunk:
                # Save current chunk
                chunk_text = "\n".join(current_chunk)
                equipment_tags = self._extract_equipment_tags(chunk_text)
                chunks.append({
                    "content": chunk_text,
                    "heading_path": heading_path,
                    "equipment_tags": equipment_tags
                })

                # Start new chunk with overlap
                overlap_paras = current_chunk[-2:] if len(current_chunk) > 2 else current_chunk[-1:]
                current_chunk = overlap_paras
                current_size = sum(len(p) for p in current_chunk)

            current_chunk.append(para)
            current_size += para_size

        # Save final chunk
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            equipment_tags = self._extract_equipment_tags(chunk_text)
            chunks.append({
                "content": chunk_text,
                "heading_path": heading_path,
                "equipment_tags": equipment_tags
            })

        return chunks

    def _extract_equipment_tags(self, text: str) -> List[str]:
        """Extract equipment tags from text"""
        tags = set()

        for pattern in self.EQUIPMENT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            tags.update(match.upper() for match in matches)

        return list(tags)

    def _detect_category(self, chunks: List[Dict]) -> str:
        """Detect document category based on content"""
        all_text = " ".join(c["content"].lower() for c in chunks)

        # Score different categories
        soo_keywords = ['sequence', 'operation', 'shall', 'when', 'enable', 'disable', 'start', 'stop', 'mode']
        commissioning_keywords = ['commissioning', 'startup', 'checkout', 'test', 'verify', 'functional']
        submittal_keywords = ['submittal', 'specification', 'manufacturer', 'model', 'catalog']

        soo_score = sum(1 for kw in soo_keywords if kw in all_text)
        commissioning_score = sum(1 for kw in commissioning_keywords if kw in all_text)
        submittal_score = sum(1 for kw in submittal_keywords if kw in all_text)

        if soo_score >= 3:
            return "SEQUENCE_OF_OPERATION"
        elif commissioning_score >= 3:
            return "COMMISSIONING"
        elif submittal_score >= 2:
            return "SUBMITTAL"

        return "OTHER"


word_processor = WordProcessor()
```

**Step 2: Verify processor**

Run: `docker-compose exec backend python -c "from app.services.word_processor import word_processor; print('OK')"`
Expected: Prints "OK"

**Step 3: Commit**

```bash
git add backend/app/services/word_processor.py
git commit -m "feat: add Word processor for parsing docx files"
```

---

### Task 8: Create Supplementary Processor Orchestrator

**Files:**
- Create: `backend/app/services/supplementary_processor.py`

**Step 1: Create orchestrator service**

Create `backend/app/services/supplementary_processor.py`:

```python
import json
import logging
import os
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import (
    SupplementaryDocument, SupplementaryChunk, EquipmentData, Equipment
)
from app.services.excel_processor import excel_processor
from app.services.word_processor import word_processor
from app.services.alias_service import alias_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class SupplementaryProcessor:
    """Orchestrates processing of supplementary documents (Excel/Word)"""

    def process_document(self, db: Session, document_id: int) -> bool:
        """Process a supplementary document"""
        document = db.query(SupplementaryDocument).filter(
            SupplementaryDocument.id == document_id
        ).first()

        if not document:
            logger.error(f"Supplementary document {document_id} not found")
            return False

        try:
            document.processed = 1
            db.commit()

            logger.info(f"Processing supplementary document: {document.original_filename}")
            print(f"\n{'#'*60}")
            print(f"# SUPPLEMENTARY DOCUMENT PROCESSING")
            print(f"# ID: {document_id}")
            print(f"# File: {document.original_filename}")
            print(f"# Type: {document.document_type}")
            print(f"{'#'*60}\n")

            if document.document_type == "EXCEL":
                self._process_excel(db, document)
            elif document.document_type == "WORD":
                self._process_word(db, document)
            else:
                raise ValueError(f"Unknown document type: {document.document_type}")

            document.processed = 2
            db.commit()

            print(f"\n{'#'*60}")
            print(f"# PROCESSING COMPLETE")
            print(f"{'#'*60}\n")

            return True

        except Exception as e:
            logger.error(f"Error processing supplementary document {document_id}: {e}")
            document.processed = -1
            document.processing_error = str(e)[:1000]
            db.commit()
            raise

    def _process_excel(self, db: Session, document: SupplementaryDocument):
        """Process Excel file"""
        result = excel_processor.process_file(document.file_path)

        # Update category if auto-detected
        if result.get("detected_category") and not document.content_category:
            document.content_category = result["detected_category"]

        chunk_index = 0

        for sheet in result.get("sheets", []):
            print(f"[EXCEL] Processing sheet: {sheet['name']}")

            schema = sheet.get("schema", {})
            rows = sheet.get("rows", [])

            # Create text chunk for semantic search
            text_content = sheet.get("text_content", "")
            if text_content:
                embedding = embedding_service.generate_embedding(text_content[:5000])

                chunk = SupplementaryChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    content=text_content[:10000],  # Limit size
                    source_location=f"Sheet: {sheet['name']}",
                    equipment_tags=json.dumps([]),
                    embedding=embedding
                )
                db.add(chunk)
                chunk_index += 1

            # Extract structured data from rows
            equipment_tags_in_sheet = set()

            for row_idx, row in enumerate(rows):
                equipment_tag = excel_processor.extract_equipment_from_row(row, schema)

                if equipment_tag:
                    equipment_tags_in_sheet.add(equipment_tag)

                    # Determine data type
                    data_type = schema.get("data_type", "OTHER")
                    if data_type == "UNKNOWN":
                        data_type = "SCHEDULE_ENTRY"

                    # Fuzzy match to existing equipment
                    equipment_id = None
                    confidence = 0.0

                    if document.project_id:
                        equipment_id, confidence = alias_service.fuzzy_match(
                            db, equipment_tag, document.project_id
                        )

                        # Add alias if matched
                        if equipment_id and confidence >= 0.85:
                            alias_service.add_alias(
                                db, equipment_id, equipment_tag,
                                document.original_filename, confidence
                            )

                    # Store structured data
                    equip_data = EquipmentData(
                        document_id=document.id,
                        equipment_tag=equipment_tag,
                        equipment_id=equipment_id,
                        match_confidence=confidence,
                        data_type=data_type,
                        data_json=json.dumps(row, default=str),
                        source_location=f"Sheet '{sheet['name']}', Row {row_idx + 2}"
                    )
                    db.add(equip_data)

            print(f"[EXCEL] Sheet '{sheet['name']}': {len(rows)} rows, {len(equipment_tags_in_sheet)} equipment tags")

        db.flush()

    def _process_word(self, db: Session, document: SupplementaryDocument):
        """Process Word file"""
        result = word_processor.process_file(document.file_path)

        # Update category if auto-detected
        if result.get("detected_category") and not document.content_category:
            document.content_category = result["detected_category"]

        chunks = result.get("chunks", [])
        print(f"[WORD] Processing {len(chunks)} chunks")

        for idx, chunk_data in enumerate(chunks):
            content = chunk_data.get("content", "")
            heading_path = chunk_data.get("heading_path", "")
            equipment_tags = chunk_data.get("equipment_tags", [])

            # Generate embedding
            embedding = embedding_service.generate_embedding(content[:5000])

            chunk = SupplementaryChunk(
                document_id=document.id,
                chunk_index=idx,
                content=content,
                source_location=heading_path,
                equipment_tags=json.dumps(equipment_tags),
                embedding=embedding
            )
            db.add(chunk)

            # Create equipment_data entries for equipment mentioned in this chunk
            for tag in equipment_tags:
                # Fuzzy match
                equipment_id = None
                confidence = 0.0

                if document.project_id:
                    equipment_id, confidence = alias_service.fuzzy_match(
                        db, tag, document.project_id
                    )

                    if equipment_id and confidence >= 0.85:
                        alias_service.add_alias(
                            db, equipment_id, tag,
                            document.original_filename, confidence
                        )

                equip_data = EquipmentData(
                    document_id=document.id,
                    equipment_tag=tag,
                    equipment_id=equipment_id,
                    match_confidence=confidence,
                    data_type="SEQUENCE",
                    data_json=json.dumps({
                        "section": heading_path,
                        "content_preview": content[:200]
                    }),
                    source_location=heading_path
                )
                db.add(equip_data)

            if (idx + 1) % 10 == 0:
                print(f"[WORD] Processed {idx + 1}/{len(chunks)} chunks")

        db.flush()
        print(f"[WORD] Complete: {len(chunks)} chunks processed")


supplementary_processor = SupplementaryProcessor()
```

**Step 2: Verify processor**

Run: `docker-compose exec backend python -c "from app.services.supplementary_processor import supplementary_processor; print('OK')"`
Expected: Prints "OK"

**Step 3: Commit**

```bash
git add backend/app/services/supplementary_processor.py
git commit -m "feat: add supplementary processor orchestrator"
```

---

### Task 9: Create Supplementary API Routes

**Files:**
- Create: `backend/app/api/routes/supplementary.py`
- Modify: `backend/app/main.py`

**Step 1: Create API routes**

Create `backend/app/api/routes/supplementary.py`:

```python
import os
import shutil
import uuid
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.database import SupplementaryDocument, SupplementaryChunk, EquipmentData, Project
from app.models.schemas import (
    SupplementaryDocumentResponse,
    SupplementaryDocumentDetail,
    SupplementaryUploadResponse,
    SupplementaryChunkResponse,
    EquipmentDataResponse
)
from app.services.supplementary_processor import supplementary_processor
from app.config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.docx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def process_supplementary_task(document_id: int):
    """Background task to process supplementary document"""
    db = SessionLocal()
    try:
        supplementary_processor.process_document(db, document_id)
    finally:
        db.close()


def get_document_type(filename: str) -> str:
    """Determine document type from extension"""
    ext = os.path.splitext(filename)[1].lower()
    if ext in {'.xlsx', '.xls', '.csv'}:
        return "EXCEL"
    elif ext == '.docx':
        return "WORD"
    return "UNKNOWN"


@router.post("/projects/{project_id}/supplementary", response_model=SupplementaryUploadResponse)
async def upload_supplementary(
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    content_category: str = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a supplementary document (Excel/Word) to a project"""

    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Seek back to start

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024} MB"
        )

    # Save file
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"

    # Create supplementary subdirectory
    supp_dir = os.path.join(settings.upload_dir, "supplementary")
    os.makedirs(supp_dir, exist_ok=True)

    file_path = os.path.join(supp_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create database record
    document_type = get_document_type(file.filename)

    document = SupplementaryDocument(
        project_id=project_id,
        filename=filename,
        original_filename=file.filename,
        document_type=document_type,
        content_category=content_category,
        file_path=file_path,
        file_size=file_size,
        processed=0
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Start background processing
    background_tasks.add_task(process_supplementary_task, document.id)

    return SupplementaryUploadResponse(
        document_id=document.id,
        filename=file.filename,
        document_type=document_type,
        message="Document uploaded successfully. Processing started."
    )


@router.get("/projects/{project_id}/supplementary", response_model=List[SupplementaryDocumentResponse])
async def list_supplementary(
    project_id: int,
    db: Session = Depends(get_db)
):
    """List all supplementary documents in a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = db.query(SupplementaryDocument).filter(
        SupplementaryDocument.project_id == project_id
    ).order_by(SupplementaryDocument.created_at.desc()).all()

    return documents


@router.get("/supplementary/{document_id}", response_model=SupplementaryDocumentDetail)
async def get_supplementary(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get supplementary document details with extracted data"""
    document = db.query(SupplementaryDocument).filter(
        SupplementaryDocument.id == document_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get chunks and equipment data
    chunks = db.query(SupplementaryChunk).filter(
        SupplementaryChunk.document_id == document_id
    ).order_by(SupplementaryChunk.chunk_index).all()

    equipment_data = db.query(EquipmentData).filter(
        EquipmentData.document_id == document_id
    ).all()

    return SupplementaryDocumentDetail(
        id=document.id,
        project_id=document.project_id,
        filename=document.filename,
        original_filename=document.original_filename,
        document_type=document.document_type,
        content_category=document.content_category,
        file_path=document.file_path,
        file_size=document.file_size,
        processed=document.processed,
        processing_error=document.processing_error,
        created_at=document.created_at,
        chunks=[SupplementaryChunkResponse(
            id=c.id,
            chunk_index=c.chunk_index,
            content=c.content,
            source_location=c.source_location,
            equipment_tags=c.equipment_tags
        ) for c in chunks],
        equipment_data=[EquipmentDataResponse(
            id=d.id,
            equipment_tag=d.equipment_tag,
            equipment_id=d.equipment_id,
            match_confidence=d.match_confidence,
            data_type=d.data_type,
            data_json=d.data_json,
            source_location=d.source_location
        ) for d in equipment_data]
    )


@router.delete("/supplementary/{document_id}")
async def delete_supplementary(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a supplementary document"""
    document = db.query(SupplementaryDocument).filter(
        SupplementaryDocument.id == document_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    # Delete record (cascades to chunks and equipment_data)
    db.delete(document)
    db.commit()

    return {"message": f"Supplementary document {document_id} deleted successfully"}


@router.post("/supplementary/{document_id}/reprocess")
async def reprocess_supplementary(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Re-process a supplementary document"""
    document = db.query(SupplementaryDocument).filter(
        SupplementaryDocument.id == document_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clear existing data
    db.query(SupplementaryChunk).filter(
        SupplementaryChunk.document_id == document_id
    ).delete()
    db.query(EquipmentData).filter(
        EquipmentData.document_id == document_id
    ).delete()

    # Reset status
    document.processed = 0
    document.processing_error = None
    db.commit()

    # Start processing
    background_tasks.add_task(process_supplementary_task, document.id)

    return {"message": f"Reprocessing started for document {document_id}"}
```

**Step 2: Register routes in main.py**

Add to `backend/app/main.py` imports:

```python
from app.api.routes import documents, search, equipment, health, projects, conversations, supplementary
```

Add router after conversations:

```python
app.include_router(supplementary.router, prefix="/api", tags=["Supplementary"])
```

**Step 3: Verify API starts**

Run: `docker-compose up -d backend && sleep 5 && curl http://localhost:8000/health`
Expected: Returns health check response

**Step 4: Commit**

```bash
git add backend/app/api/routes/supplementary.py backend/app/main.py
git commit -m "feat: add supplementary document API endpoints"
```

---

## Phase 2: Enhanced Search & RAG

### Task 10: Update Search Service for Multi-Source

**Files:**
- Modify: `backend/app/services/search_service.py`

**Step 1: Add supplementary chunk search method**

Add this method to the `SearchService` class in `backend/app/services/search_service.py`:

```python
def _supplementary_semantic_search(
    self,
    db: Session,
    query: str,
    limit: int,
    project_id: int = None
) -> List[SearchResult]:
    """Search supplementary document chunks by semantic similarity"""
    from app.models.database import SupplementaryDocument, SupplementaryChunk

    if project_id is None:
        return []

    query_embedding = embedding_service.generate_embedding(query)

    sql = text("""
        SELECT
            sc.id,
            sc.document_id,
            sc.content,
            sc.source_location,
            sc.equipment_tags,
            sd.original_filename,
            sd.document_type,
            sd.content_category,
            1 - (sc.embedding <=> CAST(:embedding AS vector)) as similarity
        FROM supplementary_chunks sc
        JOIN supplementary_documents sd ON sc.document_id = sd.id
        WHERE sd.project_id = :project_id
          AND sc.embedding IS NOT NULL
        ORDER BY sc.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    result = db.execute(sql, {
        "embedding": str(query_embedding),
        "project_id": project_id,
        "limit": limit
    })

    results = []
    for row in result:
        # Create a pseudo-document response for supplementary docs
        doc_response = DocumentResponse(
            id=row.document_id,
            filename=row.original_filename,
            original_filename=row.original_filename,
            title=f"[{row.document_type}] {row.original_filename}",
            drawing_number=None,
            revision=None,
            system=row.content_category,
            area=None,
            file_size=0,
            page_count=0,
            upload_date=None,
            processed=2
        )

        snippet = row.content[:300] + "..." if row.content and len(row.content) > 300 else row.content

        results.append(SearchResult(
            equipment=None,
            document=doc_response,
            page_number=0,  # Supplementary docs don't have pages
            relevance_score=float(row.similarity),
            snippet=f"[{row.source_location}] {snippet}",
            match_type="supplementary_semantic"
        ))

    return results
```

**Step 2: Add equipment_data search method**

Add this method to the `SearchService` class:

```python
def _equipment_data_search(
    self,
    db: Session,
    equipment_tags: List[str],
    project_id: int,
    data_types: List[str] = None
) -> List[Dict]:
    """Search structured equipment data"""
    from app.models.database import EquipmentData, SupplementaryDocument

    query = db.query(EquipmentData).join(SupplementaryDocument).filter(
        SupplementaryDocument.project_id == project_id
    )

    # Filter by equipment tags
    if equipment_tags:
        from sqlalchemy import or_, func
        tag_filters = [func.upper(EquipmentData.equipment_tag) == tag.upper() for tag in equipment_tags]
        query = query.filter(or_(*tag_filters))

    # Filter by data types if specified
    if data_types:
        query = query.filter(EquipmentData.data_type.in_(data_types))

    results = query.all()

    return [{
        "equipment_tag": r.equipment_tag,
        "data_type": r.data_type,
        "data_json": r.data_json,
        "source_location": r.source_location,
        "document_name": r.document.original_filename if r.document else None,
        "match_confidence": r.match_confidence
    } for r in results]
```

**Step 3: Update main search method**

In the `search` method, add supplementary search after semantic search. Add this code block after the semantic search section (around line 85):

```python
        # 5. Supplementary document search
        if project_id and len(results) < limit:
            supp_results = self._supplementary_semantic_search(db, query, limit - len(results), project_id)
            for r in supp_results:
                key = (r.document.id, r.snippet[:50] if r.snippet else "")  # Use snippet as unique key
                if key not in existing_pages:
                    existing_pages.add(key)
                    results.append(r)
```

**Step 4: Commit**

```bash
git add backend/app/services/search_service.py
git commit -m "feat: add supplementary document search to search service"
```

---

### Task 11: Update RAG Service for Enhanced Context

**Files:**
- Modify: `backend/app/services/rag_service.py`

**Step 1: Add equipment data context builder**

Add this method to the `RAGService` class:

```python
def _build_equipment_data_context(self, db: Session, equipment_tags: List[str], project_id: int) -> str:
    """Build context from structured equipment data"""
    from app.services.search_service import search_service

    if not equipment_tags or not project_id:
        return ""

    parts = []

    # Get IO points and alarms
    io_data = search_service._equipment_data_search(
        db, equipment_tags, project_id,
        data_types=["IO_POINT", "ALARM"]
    )

    if io_data:
        parts.append("=== IO POINTS AND ALARMS ===")
        for d in io_data:
            import json
            try:
                data = json.loads(d["data_json"])
                parts.append(f"Equipment: {d['equipment_tag']}")
                parts.append(f"  Type: {d['data_type']}")
                parts.append(f"  Data: {data}")
                parts.append(f"  Source: {d['document_name']}, {d['source_location']}")
            except:
                pass

    # Get specifications
    spec_data = search_service._equipment_data_search(
        db, equipment_tags, project_id,
        data_types=["SPECIFICATION", "SCHEDULE_ENTRY"]
    )

    if spec_data:
        parts.append("\n=== EQUIPMENT SPECIFICATIONS ===")
        for d in spec_data:
            import json
            try:
                data = json.loads(d["data_json"])
                parts.append(f"Equipment: {d['equipment_tag']}")
                parts.append(f"  {data}")
                parts.append(f"  Source: {d['document_name']}")
            except:
                pass

    # Get sequences
    seq_data = search_service._equipment_data_search(
        db, equipment_tags, project_id,
        data_types=["SEQUENCE"]
    )

    if seq_data:
        parts.append("\n=== SEQUENCE OF OPERATION ===")
        for d in seq_data[:3]:  # Limit to avoid context overload
            import json
            try:
                data = json.loads(d["data_json"])
                parts.append(f"Equipment: {d['equipment_tag']}")
                parts.append(f"  Section: {data.get('section', 'N/A')}")
                parts.append(f"  {data.get('content_preview', '')}")
                parts.append(f"  Source: {d['document_name']}")
            except:
                pass

    return "\n".join(parts)
```

**Step 2: Update query method to include equipment data context**

In the `query` method, add equipment data context after graph context (around line 75). Add this code:

```python
        # Build equipment data context from supplementary documents
        equipment_data_context = ""
        if equipment_tags and project_id:
            equipment_data_context = self._build_equipment_data_context(db, equipment_tags, project_id)
            if equipment_data_context:
                print(f"[RAG Query] Equipment data context: {len(equipment_data_context)} chars")
```

**Step 3: Update context building to include supplementary data**

Modify the `_build_context` method to accept and include equipment data context. Update the method signature and add:

```python
def _build_context(self, results: List[SearchResult], additional_context: dict) -> str:
    """Build context string for LLM"""
    parts = []

    # Add equipment data context first (structured data from Excel/Word)
    if "equipment_data_context" in additional_context and additional_context["equipment_data_context"]:
        parts.append(additional_context["equipment_data_context"])
        parts.append("")

    # Add graph-based context
    if "graph_context" in additional_context and additional_context["graph_context"]:
        parts.append(additional_context["graph_context"])
        parts.append("")

    # Rest of the method remains the same...
```

Also update the call to `_build_context` in the `query` method to include the new context:

```python
        # Build context with graph data and equipment data
        context = self._build_context(search_response.results, {
            "graph_context": graph_context,
            "equipment_data_context": equipment_data_context
        })
```

**Step 4: Commit**

```bash
git add backend/app/services/rag_service.py
git commit -m "feat: enhance RAG with supplementary document context"
```

---

## Phase 3: Frontend Integration

### Task 12: Add Supplementary API Client

**Files:**
- Create: `frontend-vue/src/api/supplementary.ts`

**Step 1: Create API client**

Create `frontend-vue/src/api/supplementary.ts`:

```typescript
import { api } from './index'

export interface SupplementaryDocument {
  id: number
  project_id: number | null
  filename: string
  original_filename: string
  document_type: 'EXCEL' | 'WORD'
  content_category: string | null
  file_path: string
  file_size: number | null
  processed: number
  processing_error: string | null
  created_at: string
}

export interface SupplementaryChunk {
  id: number
  chunk_index: number
  content: string | null
  source_location: string | null
  equipment_tags: string | null
}

export interface EquipmentDataEntry {
  id: number
  equipment_tag: string
  equipment_id: number | null
  match_confidence: number | null
  data_type: string
  data_json: string
  source_location: string | null
}

export interface SupplementaryDocumentDetail extends SupplementaryDocument {
  chunks: SupplementaryChunk[]
  equipment_data: EquipmentDataEntry[]
}

export interface UploadResponse {
  document_id: number
  filename: string
  document_type: string
  message: string
}

export async function listByProject(projectId: number): Promise<SupplementaryDocument[]> {
  const response = await api.get(`/projects/${projectId}/supplementary`)
  return response.data
}

export async function upload(
  projectId: number,
  file: File,
  contentCategory?: string
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (contentCategory) {
    formData.append('content_category', contentCategory)
  }

  const response = await api.post(`/projects/${projectId}/supplementary`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

export async function getDetail(documentId: number): Promise<SupplementaryDocumentDetail> {
  const response = await api.get(`/supplementary/${documentId}`)
  return response.data
}

export async function deleteDocument(documentId: number): Promise<void> {
  await api.delete(`/supplementary/${documentId}`)
}

export async function reprocess(documentId: number): Promise<void> {
  await api.post(`/supplementary/${documentId}/reprocess`)
}
```

**Step 2: Commit**

```bash
git add frontend-vue/src/api/supplementary.ts
git commit -m "feat: add supplementary documents API client"
```

---

### Task 13: Create Supplementary Documents List Component

**Files:**
- Create: `frontend-vue/src/components/documents/SupplementaryList.vue`

**Step 1: Create component**

Create `frontend-vue/src/components/documents/SupplementaryList.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import {
  DocumentIcon,
  TableCellsIcon,
  TrashIcon,
  ArrowPathIcon,
  CloudArrowUpIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from '@heroicons/vue/24/outline'
import * as supplementaryApi from '@/api/supplementary'
import type { SupplementaryDocument } from '@/api/supplementary'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const props = defineProps<{
  projectId: number
}>()

const emit = defineEmits<{
  upload: []
}>()

const documents = ref<SupplementaryDocument[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const showDeleteConfirm = ref(false)
const documentToDelete = ref<SupplementaryDocument | null>(null)

async function loadDocuments() {
  loading.value = true
  error.value = null
  try {
    documents.value = await supplementaryApi.listByProject(props.projectId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load documents'
  } finally {
    loading.value = false
  }
}

function getIcon(docType: string) {
  return docType === 'EXCEL' ? TableCellsIcon : DocumentIcon
}

function getStatusIcon(processed: number) {
  switch (processed) {
    case 2: return CheckCircleIcon
    case -1: return XCircleIcon
    default: return ClockIcon
  }
}

function getStatusColor(processed: number) {
  switch (processed) {
    case 2: return 'text-green-500'
    case -1: return 'text-red-500'
    default: return 'text-yellow-500'
  }
}

function getCategoryLabel(category: string | null) {
  if (!category) return 'Other'
  return category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

function confirmDelete(doc: SupplementaryDocument) {
  documentToDelete.value = doc
  showDeleteConfirm.value = true
}

async function deleteDocument() {
  if (!documentToDelete.value) return
  try {
    await supplementaryApi.deleteDocument(documentToDelete.value.id)
    showDeleteConfirm.value = false
    documentToDelete.value = null
    await loadDocuments()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete'
  }
}

async function retryDocument(doc: SupplementaryDocument) {
  try {
    await supplementaryApi.reprocess(doc.id)
    await loadDocuments()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to retry'
  }
}

onMounted(() => {
  loadDocuments()
})

watch(() => props.projectId, () => {
  loadDocuments()
})

// Poll for processing updates
const pollInterval = setInterval(async () => {
  const hasProcessing = documents.value.some(d => d.processed === 0 || d.processed === 1)
  if (hasProcessing) {
    documents.value = await supplementaryApi.listByProject(props.projectId)
  }
}, 5000)

// Cleanup on unmount
import { onUnmounted } from 'vue'
onUnmounted(() => {
  clearInterval(pollInterval)
})
</script>

<template>
  <div class="supplementary-list">
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-8">
      <LoadingSpinner size="medium" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-red-600 text-center py-4">
      {{ error }}
    </div>

    <!-- Empty State -->
    <div
      v-else-if="documents.length === 0"
      class="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600"
    >
      <TableCellsIcon class="h-12 w-12 mx-auto text-gray-400 mb-3" />
      <p class="text-gray-600 dark:text-gray-400 mb-4">No supplementary documents yet</p>
      <button
        type="button"
        class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        @click="emit('upload')"
      >
        <CloudArrowUpIcon class="h-5 w-5 mr-2" />
        Upload Excel or Word
      </button>
    </div>

    <!-- Document Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow"
      >
        <div class="flex items-start gap-3">
          <div class="p-2 bg-gray-100 dark:bg-gray-700 rounded-lg">
            <component :is="getIcon(doc.document_type)" class="h-6 w-6 text-gray-600 dark:text-gray-300" />
          </div>
          <div class="flex-1 min-w-0">
            <h4 class="font-medium text-gray-900 dark:text-white truncate">
              {{ doc.original_filename }}
            </h4>
            <div class="flex items-center gap-2 mt-1">
              <span class="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">
                {{ doc.document_type }}
              </span>
              <span class="text-xs text-gray-500 dark:text-gray-400">
                {{ getCategoryLabel(doc.content_category) }}
              </span>
            </div>
            <div class="flex items-center gap-1 mt-2">
              <component
                :is="getStatusIcon(doc.processed)"
                class="h-4 w-4"
                :class="getStatusColor(doc.processed)"
              />
              <span class="text-xs" :class="getStatusColor(doc.processed)">
                {{ doc.processed === 2 ? 'Processed' : doc.processed === -1 ? 'Error' : 'Processing...' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
          <button
            v-if="doc.processed === -1"
            type="button"
            class="p-1.5 text-gray-400 hover:text-blue-600 rounded"
            title="Retry processing"
            @click="retryDocument(doc)"
          >
            <ArrowPathIcon class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="p-1.5 text-gray-400 hover:text-red-600 rounded"
            title="Delete"
            @click="confirmDelete(doc)"
          >
            <TrashIcon class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div
      v-if="showDeleteConfirm"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">Delete Document?</h3>
        <p class="text-gray-600 dark:text-gray-400 mb-4">
          Are you sure you want to delete "{{ documentToDelete?.original_filename }}"?
          This will remove all extracted data.
        </p>
        <div class="flex justify-end gap-3">
          <button
            type="button"
            class="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
            @click="showDeleteConfirm = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 text-white bg-red-600 rounded-lg hover:bg-red-700"
            @click="deleteDocument"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend-vue/src/components/documents/SupplementaryList.vue
git commit -m "feat: add SupplementaryList component"
```

---

### Task 14: Update Project Documents View with Tabs

**Files:**
- Modify: `frontend-vue/src/views/ProjectDocumentsView.vue`

**Step 1: Add imports for supplementary components**

Add to the imports section:

```typescript
import SupplementaryList from '@/components/documents/SupplementaryList.vue'
import * as supplementaryApi from '@/api/supplementary'
```

**Step 2: Add supplementary state and tab management**

Add to the state section:

```typescript
const activeTab = ref<'drawings' | 'supplementary'>('drawings')
const showSupplementaryUpload = ref(false)
const uploadingSupplementary = ref(false)
const selectedCategory = ref<string>('')
const supplementaryFileRef = ref<HTMLInputElement | null>(null)

const CONTENT_CATEGORIES = [
  { value: 'IO_LIST', label: 'IO List' },
  { value: 'EQUIPMENT_SCHEDULE', label: 'Equipment Schedule' },
  { value: 'SEQUENCE_OF_OPERATION', label: 'Sequence of Operation' },
  { value: 'COMMISSIONING', label: 'Commissioning Guide' },
  { value: 'SUBMITTAL', label: 'Submittal' },
  { value: 'OTHER', label: 'Other' },
]
```

**Step 3: Add supplementary upload handlers**

Add these methods:

```typescript
function triggerSupplementaryUpload() {
  showSupplementaryUpload.value = true
}

function selectSupplementaryFile() {
  supplementaryFileRef.value?.click()
}

async function handleSupplementaryUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!['xlsx', 'xls', 'csv', 'docx'].includes(ext || '')) {
    error.value = 'Only Excel (.xlsx, .xls, .csv) and Word (.docx) files are supported'
    return
  }

  uploadingSupplementary.value = true
  error.value = null

  try {
    await supplementaryApi.upload(
      projectId.value,
      file,
      selectedCategory.value || undefined
    )
    showSupplementaryUpload.value = false
    selectedCategory.value = ''
    // Reload will happen via SupplementaryList component
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to upload'
  } finally {
    uploadingSupplementary.value = false
    if (input) input.value = ''
  }
}
```

**Step 4: Update template with tabs**

Replace the header section and add tabs. Update the template to include:

```vue
<!-- Tab Navigation -->
<div class="flex border-b border-gray-200 dark:border-gray-700 mb-6">
  <button
    type="button"
    class="px-4 py-2 font-medium border-b-2 transition-colors"
    :class="activeTab === 'drawings'
      ? 'border-blue-600 text-blue-600'
      : 'border-transparent text-gray-500 hover:text-gray-700'"
    @click="activeTab = 'drawings'"
  >
    Drawings ({{ documents.length }})
  </button>
  <button
    type="button"
    class="px-4 py-2 font-medium border-b-2 transition-colors"
    :class="activeTab === 'supplementary'
      ? 'border-blue-600 text-blue-600'
      : 'border-transparent text-gray-500 hover:text-gray-700'"
    @click="activeTab = 'supplementary'"
  >
    Supplementary
  </button>
</div>

<!-- Drawings Tab Content -->
<div v-if="activeTab === 'drawings'">
  <!-- existing documents grid -->
</div>

<!-- Supplementary Tab Content -->
<div v-else>
  <div class="flex justify-end mb-4">
    <button
      type="button"
      class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      @click="triggerSupplementaryUpload"
    >
      <CloudArrowUpIcon class="h-5 w-5 mr-2" />
      Upload Excel/Word
    </button>
  </div>
  <SupplementaryList
    :project-id="projectId"
    @upload="triggerSupplementaryUpload"
  />
</div>

<!-- Supplementary Upload Modal -->
<div
  v-if="showSupplementaryUpload"
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
      Upload Supplementary Document
    </h3>

    <div class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Document Category
        </label>
        <select
          v-model="selectedCategory"
          class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
        >
          <option value="">Auto-detect</option>
          <option v-for="cat in CONTENT_CATEGORIES" :key="cat.value" :value="cat.value">
            {{ cat.label }}
          </option>
        </select>
      </div>

      <div
        class="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500"
        @click="selectSupplementaryFile"
      >
        <CloudArrowUpIcon class="h-10 w-10 mx-auto text-gray-400 mb-2" />
        <p class="text-gray-600 dark:text-gray-400">
          Click to select Excel or Word file
        </p>
        <p class="text-xs text-gray-500 mt-1">
          .xlsx, .xls, .csv, .docx
        </p>
      </div>

      <input
        ref="supplementaryFileRef"
        type="file"
        accept=".xlsx,.xls,.csv,.docx"
        class="hidden"
        @change="handleSupplementaryUpload"
      />
    </div>

    <div class="flex justify-end gap-3 mt-6">
      <button
        type="button"
        class="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200"
        :disabled="uploadingSupplementary"
        @click="showSupplementaryUpload = false"
      >
        Cancel
      </button>
    </div>
  </div>
</div>
```

**Step 5: Commit**

```bash
git add frontend-vue/src/views/ProjectDocumentsView.vue
git commit -m "feat: add supplementary documents tab to project documents view"
```

---

### Task 15: Rebuild and Test

**Step 1: Rebuild backend**

Run: `docker-compose build backend`
Expected: Build succeeds

**Step 2: Restart services**

Run: `docker-compose up -d`
Expected: All services start

**Step 3: Run migration**

```bash
docker cp scripts/migrations/002_supplementary_documents.sql electric_rag-db-1:/tmp/
docker-compose exec db psql -U postgres -d electric_rag -f /tmp/002_supplementary_documents.sql
```
Expected: Tables created

**Step 4: Test API**

Run: `curl http://localhost:8000/api/projects/1/supplementary`
Expected: Returns empty array `[]`

**Step 5: Commit final state**

```bash
git add -A
git commit -m "feat: complete supplementary documents feature - Phase 1-3"
```

---

## Verification Checklist

After completing all tasks, verify:

1. [ ] Backend starts without errors
2. [ ] Migration creates all tables (supplementary_documents, supplementary_chunks, equipment_data, equipment_aliases, equipment_profiles)
3. [ ] Can upload Excel file via API
4. [ ] Can upload Word file via API
5. [ ] Processing extracts chunks and equipment data
6. [ ] Frontend shows Supplementary tab
7. [ ] Upload modal works with category selection
8. [ ] Documents list shows upload status
9. [ ] Search returns results from supplementary documents
10. [ ] RAG answers include supplementary document context

---

## Summary

This plan implements supplementary document support in 15 tasks across 3 phases:

- **Phase 1 (Tasks 1-9):** Foundation - dependencies, database, models, processors, API
- **Phase 2 (Tasks 10-11):** Enhanced Search & RAG - multi-source search, context building
- **Phase 3 (Tasks 12-15):** Frontend - API client, components, integration, testing

Each task is a focused unit of work with clear steps and verification commands.
