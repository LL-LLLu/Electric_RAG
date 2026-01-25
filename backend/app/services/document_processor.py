import json
import logging
from sqlalchemy.orm import Session

from app.models.database import Document, Page, Equipment, EquipmentLocation, EquipmentRelationship
from app.services.ocr_service import ocr_service
from app.services.extraction_service import extraction_service, ExtractedEquipment
from app.services.embedding_service import embedding_service
from app.services.ai_analysis_service import ai_analysis_service

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Orchestrates the full document processing pipeline"""

    def process_document(self, db: Session, document_id: int) -> bool:
        """Process a document: OCR -> Extract -> Index"""
        import time

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return False

        try:
            document.processed = 1
            db.commit()

            print(f"\n{'#'*60}")
            print(f"# DOCUMENT PROCESSING STARTED")
            print(f"# ID: {document_id}")
            print(f"# File: {document.original_filename}")
            print(f"# Size: {document.file_size / 1024 / 1024:.1f} MB")
            print(f"{'#'*60}\n")

            pipeline_start = time.time()
            logger.info(f"Processing document: {document.filename}")

            # Step 1: OCR
            print(f"\n[PIPELINE] Step 1/3: Text Extraction")
            print(f"-" * 40)
            step1_start = time.time()

            pages_data = ocr_service.process_document(document.file_path, document_id)
            document.page_count = len(pages_data)
            document.pages_processed = 0
            db.commit()

            print(f"[PIPELINE] Step 1 completed in {time.time() - step1_start:.1f}s")

            # Step 2: Process each page with AI analysis
            print(f"\n[PIPELINE] Step 2/4: AI Analysis & Equipment Extraction")
            print(f"-" * 40)
            step2_start = time.time()

            all_equipment: dict[str, ExtractedEquipment] = {}
            all_relationships = []
            all_ai_analyses = []

            for page_data in pages_data:
                page_num = page_data["page_number"]
                page_start = time.time()

                # AI Analysis - extract equipment using LLM
                ai_result = ai_analysis_service.analyze_page(
                    page_data["ocr_text"],
                    page_num,
                    document.original_filename
                )
                all_ai_analyses.append(ai_result)

                # Also use regex-based extraction as backup
                equipment_list = extraction_service.extract_equipment_tags(
                    page_data["ocr_text"],
                    page_data["elements"]
                )

                # Merge AI-detected equipment with regex-detected
                ai_equipment_tags = ai_result.get("equipment", [])
                for tag in ai_equipment_tags:
                    # Create ExtractedEquipment for AI-detected tags not found by regex
                    if tag and not any(eq.tag == tag for eq in equipment_list):
                        from app.services.extraction_service import ExtractedEquipment
                        equipment_list.append(ExtractedEquipment(
                            tag=tag,
                            equipment_type="OTHER",
                            context=ai_result.get("analysis", ""),
                            bbox=None
                        ))

                for eq in equipment_list:
                    if eq.tag not in all_equipment:
                        all_equipment[eq.tag] = eq

                equipment_tags = [eq.tag for eq in equipment_list]

                # Generate embedding using AI analysis + OCR text for better semantic search
                enhanced_text = f"{ai_result.get('analysis', '')} {page_data['ocr_text']}"
                text_for_embedding = embedding_service.prepare_page_text_for_embedding(
                    enhanced_text,
                    equipment_tags
                )
                embed_start = time.time()
                embedding = embedding_service.generate_embedding(text_for_embedding)
                embed_time = time.time() - embed_start

                print(f"[PIPELINE] Page {page_num}/{document.page_count} | {len(equipment_list)} equipment | embed:{embed_time:.2f}s | total:{time.time()-page_start:.2f}s")

                page = Page(
                    document_id=document_id,
                    page_number=page_data["page_number"],
                    ocr_text=page_data["ocr_text"],
                    processed_text=text_for_embedding,
                    ai_analysis=ai_result.get("analysis", ""),
                    ai_equipment_list=json.dumps(ai_equipment_tags),
                    image_path=page_data["image_path"],
                    embedding=embedding
                )
                db.add(page)
                db.flush()

                for eq in equipment_list:
                    # For project-scoped equipment, query by tag AND project_id
                    equipment_query = db.query(Equipment).filter(Equipment.tag == eq.tag)
                    if document.project_id:
                        equipment_query = equipment_query.filter(Equipment.project_id == document.project_id)
                    equipment = equipment_query.first()

                    if not equipment:
                        equipment = Equipment(
                            tag=eq.tag,
                            equipment_type=eq.equipment_type,
                            description=eq.context[:500] if eq.context else None,
                            document_id=document_id,
                            primary_page=page_data["page_number"],
                            project_id=document.project_id
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

                # Extract relationships from AI analysis
                ai_relationships = ai_result.get("relationships", [])
                equipment_tags = list(all_equipment.keys())
                relationships = extraction_service.extract_relationships(
                    page_data["ocr_text"],
                    equipment_tags
                )
                for rel in relationships:
                    rel["document_id"] = document_id
                    rel["page_number"] = page_data["page_number"]
                all_relationships.extend(relationships)

                # Update progress
                document.pages_processed = page_num
                db.commit()
                logger.info(f"Document {document_id}: Processed page {page_num}/{document.page_count}")

            print(f"[PIPELINE] Step 2 completed in {time.time() - step2_start:.1f}s")
            print(f"[PIPELINE] Total equipment found: {len(all_equipment)}")
            print(f"[PIPELINE] Total relationships found: {len(all_relationships)}")

            # Step 3: Generate document summary
            print(f"\n[PIPELINE] Step 3/4: Generating Document Summary")
            print(f"-" * 40)
            step3_start = time.time()

            doc_summary = ai_analysis_service.generate_document_summary(
                all_ai_analyses,
                document.original_filename
            )
            if doc_summary:
                document.title = doc_summary[:500]  # Store summary as title
                print(f"[PIPELINE] Document summary: {doc_summary[:200]}...")

            print(f"[PIPELINE] Step 3 completed in {time.time() - step3_start:.1f}s")

            # Step 4: Save relationships
            print(f"\n[PIPELINE] Step 4/4: Saving Relationships")
            print(f"-" * 40)
            step4_start = time.time()
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

            print(f"[PIPELINE] Step 4 completed in {time.time() - step4_start:.1f}s")

            total_time = time.time() - pipeline_start
            print(f"\n{'#'*60}")
            print(f"# DOCUMENT PROCESSING COMPLETED")
            print(f"# Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
            print(f"# Pages: {len(pages_data)}")
            print(f"# Equipment: {len(all_equipment)}")
            print(f"# Relationships: {len(all_relationships)}")
            print(f"{'#'*60}\n")

            logger.info(f"Document {document_id} processed successfully. "
                       f"Pages: {len(pages_data)}, Equipment: {len(all_equipment)}")
            return True

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            document.processed = -1
            document.processing_error = str(e)[:1000]  # Limit error message length
            db.commit()
            raise


document_processor = DocumentProcessor()
