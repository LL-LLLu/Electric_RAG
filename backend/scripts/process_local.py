#!/usr/bin/env python3
"""
Local Document Pre-Processing Script

Runs the full processing pipeline locally on a machine with sufficient RAM,
then outputs a zip bundle that can be imported to the cloud server.

Usage:
    cd backend
    python scripts/process_local.py path/to/drawing.pdf -o drawing_bundle.zip

Environment:
    Needs GEMINI_API_KEY or ANTHROPIC_API_KEY for AI analysis.
    Does NOT need DATABASE_URL.
"""

import sys
import os
import json
import argparse
import logging
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Add app to path (same pattern as backend/scripts/reprocess.py)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging before importing app modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_environment(temp_dir: str):
    """Set up environment variables before importing services."""
    os.environ["UPLOAD_DIR"] = temp_dir
    # Prevent services from requiring a database
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///unused.db"


def process_document(file_path: str, output_path: str) -> None:
    """Run the full processing pipeline and output a zip bundle."""
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    original_filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    temp_dir = tempfile.mkdtemp(prefix="process_local_")
    logger.info(f"Using temp directory: {temp_dir}")

    try:
        setup_environment(temp_dir)

        # Import services after environment is set up
        from app.services.ocr_service import ocr_service
        from app.services.extraction_service import extraction_service, ExtractedEquipment
        from app.services.embedding_service import embedding_service
        from app.services.ai_analysis_service import ai_analysis_service
        from app.services.vision_extraction_service import vision_extraction_service
        from PIL import Image

        pipeline_start = time.time()

        # Step 1: OCR
        logger.info("[PIPELINE] Step 1: Text Extraction (OCR)")
        step1_start = time.time()
        pages_data = ocr_service.process_document(file_path, document_id=0)
        page_count = len(pages_data)
        logger.info(f"[PIPELINE] Step 1 completed in {time.time() - step1_start:.1f}s - {page_count} pages")

        # Step 2: Process each page
        logger.info("[PIPELINE] Step 2: AI Analysis & Equipment Extraction")
        step2_start = time.time()

        all_equipment: dict = {}  # tag -> ExtractedEquipment
        all_relationships: list = []
        all_ai_analyses: list = []
        manifest_pages: list = []

        for page_data in pages_data:
            page_num = page_data["page_number"]
            page_start = time.time()

            page_manifest = {
                "page_number": page_num,
                "image_filename": f"pages/page_{page_num}.png",
                "ocr_text": page_data["ocr_text"],
                "elements": page_data.get("elements", []),
            }

            # AI Analysis
            try:
                ai_result = ai_analysis_service.analyze_page(
                    page_data["ocr_text"],
                    page_num,
                    original_filename
                )
            except Exception as e:
                logger.warning(f"AI analysis failed for page {page_num}: {e}")
                ai_result = {
                    "analysis": "",
                    "equipment": [],
                    "relationships": [],
                    "detailed_connections": [],
                    "drawing_type": None,
                }
            all_ai_analyses.append(ai_result)

            # Regex-based extraction as backup
            equipment_list = extraction_service.extract_equipment_tags(
                page_data["ocr_text"],
                page_data.get("elements", [])
            )

            # Merge AI-detected equipment with regex-detected
            # (same logic as document_processor.py:46-56)
            ai_equipment_tags = ai_result.get("equipment", [])
            for tag in ai_equipment_tags:
                if tag and not any(eq.tag == tag for eq in equipment_list):
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

            # Vision Extraction
            vision_rels = []
            try:
                if page_data.get("image_path") and os.path.exists(page_data["image_path"]):
                    with Image.open(page_data["image_path"]) as page_image:
                        page_image.load()
                        vision_rels = vision_extraction_service.process_page(
                            page_image,
                            [{"tag": eq.tag, "bbox": eq.bbox} for eq in equipment_list if eq.bbox]
                        )
                        for rel in vision_rels:
                            rel["page_number"] = page_num
                        all_relationships.extend(vision_rels)
                        if vision_rels:
                            logger.info(f"[PIPELINE] Page {page_num}: Vision found {len(vision_rels)} relationships")
            except Exception as e:
                logger.warning(f"Vision extraction failed for page {page_num}: {e}")

            # Generate embedding
            enhanced_text = f"{ai_result.get('analysis', '')} {page_data['ocr_text']}"
            text_for_embedding = embedding_service.prepare_page_text_for_embedding(
                enhanced_text,
                equipment_tags
            )
            embedding = embedding_service.generate_embedding(text_for_embedding)

            # Extract relationships from AI analysis
            ai_relationships = ai_result.get("relationships", [])
            detailed_connections = ai_result.get("detailed_connections", [])
            equipment_tags_all = list(all_equipment.keys())

            # Regex-based relationship extraction
            relationships = extraction_service.extract_relationships(
                page_data["ocr_text"],
                equipment_tags_all
            )
            for rel in relationships:
                rel["page_number"] = page_num
            all_relationships.extend(relationships)

            # Parse AI-detected relationships
            if ai_relationships:
                parsed_ai_rels = extraction_service.parse_ai_relationships(
                    ai_relationships,
                    equipment_tags_all
                )
                for rel in parsed_ai_rels:
                    rel["page_number"] = page_num
                all_relationships.extend(parsed_ai_rels)

            # Build page manifest entry
            page_manifest["ai_analysis"] = ai_result.get("analysis", "")
            page_manifest["ai_equipment_list"] = ai_equipment_tags
            page_manifest["drawing_type"] = ai_result.get("drawing_type")
            page_manifest["processed_text"] = text_for_embedding
            page_manifest["embedding"] = embedding if isinstance(embedding, list) else embedding.tolist()
            page_manifest["equipment"] = [
                {
                    "tag": eq.tag,
                    "equipment_type": eq.equipment_type,
                    "context": eq.context,
                    "bbox": eq.bbox,
                    "confidence": eq.confidence,
                }
                for eq in equipment_list
            ]
            page_manifest["relationships"] = [
                rel for rel in all_relationships
                if rel.get("page_number") == page_num
                and "source" in rel and "target" in rel
            ]
            page_manifest["detailed_connections"] = detailed_connections or []

            manifest_pages.append(page_manifest)

            logger.info(
                f"[PIPELINE] Page {page_num}/{page_count} | "
                f"{len(equipment_list)} equipment | "
                f"{time.time() - page_start:.2f}s"
            )

        logger.info(f"[PIPELINE] Step 2 completed in {time.time() - step2_start:.1f}s")

        # Step 3: Generate document summary
        logger.info("[PIPELINE] Step 3: Generating Document Summary")
        try:
            doc_summary = ai_analysis_service.generate_document_summary(
                all_ai_analyses,
                original_filename
            )
        except Exception as e:
            logger.warning(f"Document summary generation failed: {e}")
            doc_summary = ""

        total_time = time.time() - pipeline_start
        logger.info(
            f"[PIPELINE] COMPLETED - Time: {total_time:.1f}s ({total_time/60:.1f} min), "
            f"Pages: {page_count}, Equipment: {len(all_equipment)}, "
            f"Relationships: {len(all_relationships)}"
        )

        # Build manifest
        manifest = {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "document": {
                "original_filename": original_filename,
                "title": doc_summary[:500] if doc_summary else "",
                "file_size": file_size,
                "page_count": page_count,
            },
            "pages": manifest_pages,
        }

        # Package into zip
        logger.info(f"[BUNDLE] Creating zip bundle: {output_path}")
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # manifest.json
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # Original file
            zf.write(file_path, f"original{os.path.splitext(original_filename)[1]}")

            # Page images
            for page_data in pages_data:
                img_path = page_data.get("image_path")
                if img_path and os.path.exists(img_path):
                    page_num = page_data["page_number"]
                    zf.write(img_path, f"pages/page_{page_num}.png")

        bundle_size = os.path.getsize(output_path)
        logger.info(
            f"[BUNDLE] Created: {output_path} "
            f"({bundle_size / 1024 / 1024:.1f} MB, {page_count} pages, "
            f"{len(all_equipment)} equipment, {len(all_relationships)} relationships)"
        )

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        # Clean up partial output
        if os.path.exists(output_path):
            os.remove(output_path)
        sys.exit(1)
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Process an electrical drawing locally and create an import bundle."
    )
    parser.add_argument(
        "file",
        help="Path to the document (PDF or image)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output zip file path (default: <filename>_bundle.zip)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Default output name
    if args.output is None:
        base = os.path.splitext(os.path.basename(args.file))[0]
        args.output = f"{base}_bundle.zip"

    # Validate environment
    has_ai_key = bool(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )
    if not has_ai_key:
        logger.warning(
            "No GEMINI_API_KEY or ANTHROPIC_API_KEY set. "
            "AI analysis will be skipped (regex-only extraction)."
        )

    process_document(args.file, args.output)


if __name__ == "__main__":
    main()
