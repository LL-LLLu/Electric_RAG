import os
import json
import logging
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
            elif document.document_type == 'WORD':
                structured_data, chunks = word_processor.parse_file(file_path)
            else:
                raise ValueError(f"Unknown document type: {document.document_type}")

            logger.info(f"Extracted {len(structured_data)} data entries and {len(chunks)} chunks")

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
            data = json.loads(entry.data_json)

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
            from datetime import datetime
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
