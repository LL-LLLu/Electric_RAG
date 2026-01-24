import logging
from sqlalchemy.orm import Session

from app.models.database import Document, Page, Equipment, EquipmentLocation, EquipmentRelationship
from app.services.ocr_service import ocr_service
from app.services.extraction_service import extraction_service, ExtractedEquipment
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Orchestrates the full document processing pipeline"""

    def process_document(self, db: Session, document_id: int) -> bool:
        """Process a document: OCR -> Extract -> Index"""

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return False

        try:
            document.processed = 1
            db.commit()

            logger.info(f"Processing document: {document.filename}")

            # Step 1: OCR
            pages_data = ocr_service.process_document(document.file_path, document_id)
            document.page_count = len(pages_data)

            # Step 2: Process each page
            all_equipment: dict[str, ExtractedEquipment] = {}
            all_relationships = []

            for page_data in pages_data:
                equipment_list = extraction_service.extract_equipment_tags(
                    page_data["ocr_text"],
                    page_data["elements"]
                )

                for eq in equipment_list:
                    if eq.tag not in all_equipment:
                        all_equipment[eq.tag] = eq

                equipment_tags = [eq.tag for eq in equipment_list]
                text_for_embedding = embedding_service.prepare_page_text_for_embedding(
                    page_data["ocr_text"],
                    equipment_tags
                )
                embedding = embedding_service.generate_embedding(text_for_embedding)

                page = Page(
                    document_id=document_id,
                    page_number=page_data["page_number"],
                    ocr_text=page_data["ocr_text"],
                    processed_text=text_for_embedding,
                    image_path=page_data["image_path"],
                    embedding=embedding
                )
                db.add(page)
                db.flush()

                for eq in equipment_list:
                    equipment = db.query(Equipment).filter(Equipment.tag == eq.tag).first()
                    if not equipment:
                        equipment = Equipment(
                            tag=eq.tag,
                            equipment_type=eq.equipment_type,
                            description=eq.context[:500] if eq.context else None,
                            document_id=document_id,
                            primary_page=page_data["page_number"]
                        )
                        db.add(equipment)
                        db.flush()

                    location = EquipmentLocation(
                        equipment_id=equipment.id,
                        page_id=page.id,
                        context_text=eq.context[:500] if eq.context else None
                    )
                    if eq.bbox:
                        location.x_min = eq.bbox["x_min"]
                        location.y_min = eq.bbox["y_min"]
                        location.x_max = eq.bbox["x_max"]
                        location.y_max = eq.bbox["y_max"]
                    db.add(location)

                equipment_tags = list(all_equipment.keys())
                relationships = extraction_service.extract_relationships(
                    page_data["ocr_text"],
                    equipment_tags
                )
                for rel in relationships:
                    rel["document_id"] = document_id
                    rel["page_number"] = page_data["page_number"]
                all_relationships.extend(relationships)

            # Step 3: Save relationships
            for rel in all_relationships:
                source = db.query(Equipment).filter(Equipment.tag == rel["source"]).first()
                target = db.query(Equipment).filter(Equipment.tag == rel["target"]).first()

                if source and target:
                    existing = db.query(EquipmentRelationship).filter(
                        EquipmentRelationship.source_id == source.id,
                        EquipmentRelationship.target_id == target.id,
                        EquipmentRelationship.relationship_type == rel["type"]
                    ).first()

                    if not existing:
                        relationship = EquipmentRelationship(
                            source_id=source.id,
                            target_id=target.id,
                            relationship_type=rel["type"],
                            document_id=rel["document_id"],
                            page_number=rel["page_number"],
                            confidence=rel["confidence"]
                        )
                        db.add(relationship)

            document.processed = 2
            db.commit()

            logger.info(f"Document {document_id} processed successfully. "
                       f"Pages: {len(pages_data)}, Equipment: {len(all_equipment)}")
            return True

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            document.processed = -1
            db.commit()
            raise


document_processor = DocumentProcessor()
