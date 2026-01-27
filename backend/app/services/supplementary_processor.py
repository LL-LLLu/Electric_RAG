import os
import json
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import (
    SupplementaryDocument, SupplementaryChunk, EquipmentData,
    Equipment, EquipmentProfile
)
from app.services.excel_processor import excel_processor
from app.services.word_processor import word_processor
from app.services.alias_service import alias_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class SupplementaryProcessor:
    """Orchestrate processing of supplementary documents (Excel, Word)"""

    def process_document(self, db: Session, document: SupplementaryDocument) -> bool:
        """Process a supplementary document end-to-end

        Args:
            db: Database session
            document: SupplementaryDocument record to process

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Update status to processing
            document.processed = 1
            db.commit()

            logger.info(f"Processing supplementary document: {document.original_filename}")

            # Route to appropriate processor
            file_path = document.file_path
            if document.document_type == 'EXCEL':
                structured_data, chunks = excel_processor.parse_file(file_path)
                # Perform AI analysis for deeper understanding
                ai_results = excel_processor.analyze_with_ai(file_path)
            elif document.document_type == 'WORD':
                structured_data, chunks = word_processor.parse_file(file_path)
                # Perform AI analysis for deeper understanding
                ai_results = word_processor.analyze_with_ai(file_path)
            else:
                raise ValueError(f"Unknown document type: {document.document_type}")

            # Validate parser output
            if structured_data is None:
                structured_data = []
            if chunks is None:
                chunks = []

            logger.info(f"Extracted {len(structured_data)} data entries and {len(chunks)} chunks")

            # Merge AI-extracted equipment into structured data
            ai_structured_data = self._convert_ai_results_to_structured_data(ai_results, document)
            if ai_structured_data:
                logger.info(f"AI extracted {len(ai_structured_data)} additional data entries")
                structured_data.extend(ai_structured_data)

            # Get equipment list for this project for fuzzy matching
            equipment_list = db.query(Equipment).filter(
                Equipment.project_id == document.project_id
            ).all()

            # Store structured equipment data with fuzzy matching
            for data in structured_data:
                self._store_equipment_data(db, document, data, equipment_list)

            # Store and embed chunks
            for chunk in chunks:
                self._store_chunk(db, document, chunk)

            # Store AI analysis summary if available
            if ai_results and not ai_results.get('error'):
                document.ai_analysis = json.dumps(ai_results, default=str)

            # Update document status
            document.processed = 2  # Done
            db.commit()

            logger.info(f"Successfully processed document {document.id}")

            # Rebuild profiles for affected equipment
            self._rebuild_affected_profiles(db, document)

            return True

        except Exception as e:
            logger.error(f"Error processing document {document.id}: {e}")
            document.processed = -1  # Error
            document.processing_error = str(e)
            db.commit()
            return False

    def _convert_ai_results_to_structured_data(self, ai_results: dict, document: SupplementaryDocument) -> list:
        """Convert AI analysis results to structured data entries

        Args:
            ai_results: Dict from AI analysis
            document: Parent document

        Returns:
            List of structured data dicts ready for storage
        """
        structured_data = []

        if not ai_results or ai_results.get('error'):
            return structured_data

        # Process equipment from AI
        for eq in ai_results.get('equipment', []):
            if not isinstance(eq, dict):
                continue
            tag = eq.get('tag', '')
            if not tag:
                continue

            data_json = {
                'type': eq.get('type', ''),
                'description': eq.get('description', ''),
                'function': eq.get('function', ''),
                'specs': eq.get('specs', {})
            }
            # Remove empty values
            data_json = {k: v for k, v in data_json.items() if v}

            structured_data.append({
                'equipment_tag': tag,
                'data_type': 'SPECIFICATION',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        # Process IO points from AI (Excel)
        for io in ai_results.get('io_points', []):
            if not isinstance(io, dict):
                continue
            tag = io.get('tag', '')
            if not tag:
                continue

            data_json = {
                'point_name': io.get('point_name', ''),
                'io_type': io.get('io_type', ''),
                'description': io.get('description', ''),
                'range': io.get('range', '')
            }
            data_json = {k: v for k, v in data_json.items() if v}

            structured_data.append({
                'equipment_tag': tag,
                'data_type': 'IO_POINT',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        # Process alarms from AI
        for alarm in ai_results.get('alarms', []):
            if not isinstance(alarm, dict):
                continue
            tag = alarm.get('tag', '') or alarm.get('equipment_tag', '')
            if not tag:
                continue

            data_json = {
                'alarm_name': alarm.get('alarm_name', '') or alarm.get('alarm', ''),
                'category': alarm.get('category', ''),
                'setpoint': alarm.get('setpoint', ''),
                'description': alarm.get('description', ''),
                'action': alarm.get('action', '')
            }
            data_json = {k: v for k, v in data_json.items() if v}

            structured_data.append({
                'equipment_tag': tag,
                'data_type': 'ALARM',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        # Process sequences from AI (Word docs)
        for seq in ai_results.get('sequences', []):
            if not isinstance(seq, dict):
                continue
            tag = seq.get('equipment_tag', '')
            if not tag:
                continue

            data_json = {
                'mode': seq.get('mode', ''),
                'steps': seq.get('steps', [])
            }
            data_json = {k: v for k, v in data_json.items() if v}

            structured_data.append({
                'equipment_tag': tag,
                'data_type': 'SEQUENCE',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        # Process control logic from AI (Word docs)
        for ctrl in ai_results.get('control_logic', []):
            if not isinstance(ctrl, dict):
                continue
            tag = ctrl.get('equipment_tag', '')
            if not tag:
                continue

            data_json = {
                'control_type': ctrl.get('control_type', ''),
                'controlled_variable': ctrl.get('controlled_variable', ''),
                'setpoint': ctrl.get('setpoint', ''),
                'output': ctrl.get('output', '')
            }
            data_json = {k: v for k, v in data_json.items() if v}

            structured_data.append({
                'equipment_tag': tag,
                'data_type': 'SPECIFICATION',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        # Process interlocks from AI
        for intlk in ai_results.get('interlocks', []):
            if not isinstance(intlk, dict):
                continue
            tag = intlk.get('equipment_tag', '')
            if not tag:
                continue

            data_json = {
                'condition': intlk.get('condition', ''),
                'action': intlk.get('action', '')
            }
            data_json = {k: v for k, v in data_json.items() if v}

            structured_data.append({
                'equipment_tag': tag,
                'data_type': 'SPECIFICATION',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        # Process setpoints from AI (Word docs)
        for sp in ai_results.get('setpoints', []):
            if not isinstance(sp, dict):
                continue
            tag = sp.get('equipment_tag', '')
            if not tag:
                continue

            data_json = {
                'parameter': sp.get('parameter', ''),
                'value': sp.get('value', ''),
                'mode': sp.get('mode', '')
            }
            data_json = {k: v for k, v in data_json.items() if v}

            structured_data.append({
                'equipment_tag': tag,
                'data_type': 'SPECIFICATION',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        # Process relationships from AI (Excel)
        for rel in ai_results.get('relationships', []):
            if not isinstance(rel, dict):
                continue
            source = rel.get('source', '')
            target = rel.get('target', '')
            if not source or not target:
                continue

            # Store for source equipment
            data_json = {
                'relationship': rel.get('relationship', 'CONNECTED'),
                'connected_to': target
            }
            structured_data.append({
                'equipment_tag': source,
                'data_type': 'SPECIFICATION',
                'data_json': json.dumps(data_json, default=str),
                'source_location': f"AI:{document.original_filename}"
            })

        return structured_data

    def _store_equipment_data(self, db: Session, document: SupplementaryDocument,
                              data: dict, equipment_list: list) -> EquipmentData:
        """Store equipment data entry with fuzzy matching

        Args:
            db: Database session
            document: Parent document
            data: Dict with equipment_tag, data_type, data_json, source_location
            equipment_list: List of Equipment objects for fuzzy matching
        """
        equipment_tag = data['equipment_tag']

        # Try to match to existing equipment
        equipment, confidence = alias_service.find_equipment_by_tag(
            db, equipment_tag, document.project_id
        )

        equipment_id = equipment.id if equipment else None

        # Create alias if we found a match with different tag
        if equipment and equipment.tag.upper() != equipment_tag.upper():
            alias_service.create_alias(
                db, equipment.id, equipment_tag,
                source=document.original_filename,
                confidence=confidence
            )

        # Store the data entry
        entry = EquipmentData(
            document_id=document.id,
            equipment_tag=equipment_tag,
            equipment_id=equipment_id,
            match_confidence=confidence if equipment else None,
            data_type=data['data_type'],
            data_json=data['data_json'],
            source_location=data.get('source_location', '')
        )
        db.add(entry)
        db.commit()

        logger.debug(f"Stored equipment data for {equipment_tag} "
                    f"(matched: {equipment.tag if equipment else 'None'})")

        return entry

    def _store_chunk(self, db: Session, document: SupplementaryDocument,
                     chunk: dict) -> SupplementaryChunk:
        """Store a text chunk with embedding

        Args:
            db: Database session
            document: Parent document
            chunk: Dict with chunk_index, content, source_location, equipment_tags
        """
        # Generate embedding for the content
        content = chunk['content']
        try:
            embedding = embedding_service.generate_embedding(content)
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            embedding = None

        chunk_record = SupplementaryChunk(
            document_id=document.id,
            chunk_index=chunk['chunk_index'],
            content=content,
            source_location=chunk.get('source_location', ''),
            equipment_tags=chunk.get('equipment_tags'),
            embedding=embedding
        )
        db.add(chunk_record)
        db.commit()

        return chunk_record

    def _rebuild_affected_profiles(self, db: Session, document: SupplementaryDocument) -> None:
        """Rebuild equipment profiles for equipment mentioned in document

        Args:
            db: Database session
            document: The processed document
        """
        # Get all equipment IDs referenced in this document's data
        equipment_ids = db.query(EquipmentData.equipment_id).filter(
            EquipmentData.document_id == document.id,
            EquipmentData.equipment_id.isnot(None)
        ).distinct().all()

        if not equipment_ids:
            logger.debug(f"No equipment profiles to rebuild for document {document.id}")
            return

        logger.info(f"Rebuilding {len(equipment_ids)} equipment profiles for document {document.id}")

        for (eq_id,) in equipment_ids:
            self._rebuild_profile(db, eq_id)

    def _rebuild_profile(self, db: Session, equipment_id: int) -> Optional[EquipmentProfile]:
        """Rebuild the aggregated profile for an equipment

        Args:
            db: Database session
            equipment_id: Equipment ID to rebuild profile for

        Returns:
            Updated EquipmentProfile or None
        """
        equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            return None

        # Gather all data for this equipment
        data_entries = db.query(EquipmentData).filter(
            EquipmentData.equipment_id == equipment_id
        ).all()

        # Build aggregated profile
        profile_data = {
            'tag': equipment.tag,
            'type': equipment.equipment_type,
            'aliases': [a.alias for a in equipment.aliases] if equipment.aliases else [],
            'specs': {},
            'io_points': [],
            'alarms': [],
            'schedule_entries': [],
            'sequences': [],
            'documents': []
        }

        seen_docs = set()

        for entry in data_entries:
            try:
                data = json.loads(entry.data_json)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in equipment data {entry.id}: {e}")
                continue

            # Track source documents
            doc = entry.document
            if doc.id not in seen_docs:
                seen_docs.add(doc.id)
                profile_data['documents'].append({
                    'type': doc.document_type,
                    'name': doc.original_filename,
                    'location': entry.source_location
                })

            # Categorize by data type
            if entry.data_type == 'SPECIFICATION':
                profile_data['specs'].update(data)
            elif entry.data_type == 'IO_POINT':
                profile_data['io_points'].append(data)
            elif entry.data_type == 'ALARM':
                profile_data['alarms'].append(data)
            elif entry.data_type == 'SCHEDULE_ENTRY':
                profile_data['schedule_entries'].append(data)
            elif entry.data_type == 'SEQUENCE':
                profile_data['sequences'].append(data)

        # Update or create profile
        profile = db.query(EquipmentProfile).filter(
            EquipmentProfile.equipment_id == equipment_id
        ).first()

        if profile:
            profile.profile_json = json.dumps(profile_data, default=str)
            profile.last_updated = datetime.utcnow()
        else:
            profile = EquipmentProfile(
                equipment_id=equipment_id,
                profile_json=json.dumps(profile_data, default=str)
            )
            db.add(profile)

        db.commit()

        logger.info(f"Rebuilt profile for equipment {equipment.tag}")
        return profile

    def reprocess_document(self, db: Session, document_id: int) -> bool:
        """Re-process an existing document

        Args:
            db: Database session
            document_id: ID of document to reprocess

        Returns:
            True if successful, False otherwise
        """
        document = db.query(SupplementaryDocument).filter(
            SupplementaryDocument.id == document_id
        ).first()

        if not document:
            logger.error(f"Document {document_id} not found")
            return False

        # Clear existing data
        db.query(SupplementaryChunk).filter(
            SupplementaryChunk.document_id == document_id
        ).delete()
        db.query(EquipmentData).filter(
            EquipmentData.document_id == document_id
        ).delete()
        db.commit()

        return self.process_document(db, document)


# Singleton instance
supplementary_processor = SupplementaryProcessor()
