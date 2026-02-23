import os
import shutil
import uuid
import io
import json
import zipfile
import tempfile
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from PIL import Image

from app.db.session import get_db, SessionLocal
from app.api.auth import require_api_key
from app.models.database import (
    Document, Page, Equipment, EquipmentLocation,
    EquipmentRelationship, DetailedConnection, Project,
)
from app.models.schemas import (
    DocumentResponse, DocumentDetail, UploadResponse,
    DocumentProjectAssign, ImportResponse,
)
from app.services.document_processor import document_processor
from app.services.ocr_service import ocr_service
from app.config import settings
from app.api.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.webp', '.heic', '.heif'}


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension"""
    return os.path.splitext(filename.lower())[1]


def is_supported_file(filename: str) -> bool:
    """Check if file type is supported"""
    return get_file_extension(filename) in SUPPORTED_EXTENSIONS


def process_document_task(document_id: int):
    """Background task to process document"""
    db = SessionLocal()
    try:
        document_processor.process_document(db, document_id)
    finally:
        db.close()


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("5/minute")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a new electrical drawing (PDF or image)"""

    if not is_supported_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported formats: PDF, PNG, JPG, JPEG, TIFF, BMP, GIF, WEBP, HEIC"
        )

    file_id = str(uuid.uuid4())
    ext = get_file_extension(file.filename)
    filename = f"{file_id}{ext}"
    file_path = os.path.join(settings.upload_dir, filename)

    os.makedirs(settings.upload_dir, exist_ok=True)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(file_path)

    document = Document(
        filename=filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        processed=0
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(process_document_task, document.id)

    return UploadResponse(
        document_id=document.id,
        filename=file.filename,
        message="Document uploaded successfully. Processing started.",
        pages_detected=0
    )


@router.post("/project/{project_id}/upload", response_model=UploadResponse)
async def upload_document_to_project(
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a new electrical drawing (PDF or image) to a specific project"""

    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not is_supported_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported formats: PDF, PNG, JPG, JPEG, TIFF, BMP, GIF, WEBP, HEIC"
        )

    file_id = str(uuid.uuid4())
    ext = get_file_extension(file.filename)
    filename = f"{file_id}{ext}"
    file_path = os.path.join(settings.upload_dir, filename)

    os.makedirs(settings.upload_dir, exist_ok=True)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(file_path)

    document = Document(
        filename=filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        processed=0,
        project_id=project_id
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(process_document_task, document.id)

    return UploadResponse(
        document_id=document.id,
        filename=file.filename,
        message="Document uploaded successfully. Processing started.",
        pages_detected=0
    )


def _to_str(val, max_len=None):
    """Safely convert a value to string, serializing dicts/lists as JSON."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        result = json.dumps(val)
    else:
        result = str(val)
    if max_len and len(result) > max_len:
        result = result[:max_len]
    return result


# 2 GB max uncompressed size for import bundles
_MAX_BUNDLE_UNCOMPRESSED = 2 * 1024 * 1024 * 1024


@router.post("/import", response_model=ImportResponse)
@limiter.limit("5/minute")
async def import_preprocessed_bundle(
    request: Request,
    file: UploadFile = File(...),
    project_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Import a pre-processed document bundle (zip) created by process_local.py.

    Bypasses the RAM-intensive processing pipeline by importing
    pre-computed OCR, AI analysis, embeddings, and equipment data.
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip bundle")

    # Validate project if specified
    if project_id is not None:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    # Save uploaded zip to temp location
    tmp_dir = tempfile.mkdtemp(prefix="import_bundle_")
    zip_path = os.path.join(tmp_dir, "bundle.zip")
    try:
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Extract and validate zip
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if "manifest.json" not in names:
                    raise HTTPException(status_code=400, detail="Bundle missing manifest.json")

                # Security: check uncompressed size to prevent zip bombs
                total_size = sum(info.file_size for info in zf.infolist())
                if total_size > _MAX_BUNDLE_UNCOMPRESSED:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Bundle too large when decompressed ({total_size / 1024 / 1024:.0f} MB)"
                    )

                # Security: validate all member paths to prevent path traversal
                real_tmp = os.path.realpath(tmp_dir)
                for member in zf.infolist():
                    target = os.path.realpath(os.path.join(tmp_dir, member.filename))
                    if not target.startswith(real_tmp + os.sep) and target != real_tmp:
                        raise HTTPException(status_code=400, detail="Invalid path in zip bundle")

                zf.extractall(tmp_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid zip file")

        # Read and validate manifest
        with open(os.path.join(tmp_dir, "manifest.json"), "r") as f:
            manifest = json.load(f)

        if manifest.get("version") != "1.0":
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported manifest version: {manifest.get('version')}"
            )

        doc_info = manifest.get("document", {})
        pages_info = manifest.get("pages", [])
        if not pages_info:
            raise HTTPException(status_code=400, detail="Bundle contains no pages")

        # Validate embedding dimensions on all pages
        for i, pg in enumerate(pages_info):
            emb = pg.get("embedding")
            if not isinstance(emb, list) or len(emb) != 384:
                raise HTTPException(
                    status_code=400,
                    detail=f"Page {pg.get('page_number', i+1)}: expected 384-dim embedding, "
                           f"got {type(emb).__name__} of length {len(emb) if isinstance(emb, list) else 'N/A'}"
                )

        # Find the original file in the bundle (sanitize with basename)
        original_ext = os.path.splitext(doc_info.get("original_filename", ".pdf"))[1]
        original_in_bundle = f"original{original_ext}"
        if original_in_bundle not in names:
            originals = [os.path.basename(n) for n in names if os.path.basename(n).startswith("original")]
            if originals:
                original_in_bundle = originals[0]
                original_ext = os.path.splitext(original_in_bundle)[1]
            else:
                raise HTTPException(status_code=400, detail="Bundle missing original document file")

        # --- Begin import transaction ---
        try:
            # Save original file with UUID name
            file_id = str(uuid.uuid4())
            filename = f"{file_id}{original_ext}"
            dest_file_path = os.path.join(settings.upload_dir, filename)
            os.makedirs(settings.upload_dir, exist_ok=True)
            shutil.copy2(os.path.join(tmp_dir, original_in_bundle), dest_file_path)

            # Create Document record (processed=2 means done)
            document = Document(
                filename=filename,
                original_filename=doc_info.get("original_filename", "unknown"),
                title=doc_info.get("title", ""),
                file_path=dest_file_path,
                file_size=doc_info.get("file_size", os.path.getsize(dest_file_path)),
                page_count=doc_info.get("page_count", len(pages_info)),
                pages_processed=len(pages_info),
                processed=2,
                project_id=project_id,
            )
            db.add(document)
            db.flush()
            document_id = document.id

            # Create page image directory
            page_img_dir = os.path.join(settings.upload_dir, f"doc_{document_id}", "pages")
            os.makedirs(page_img_dir, exist_ok=True)

            # Copy page images
            for page_info in pages_info:
                img_filename = page_info.get("image_filename", "")
                src_img = os.path.join(tmp_dir, img_filename)
                if os.path.exists(src_img):
                    page_num = page_info["page_number"]
                    dest_img = os.path.join(page_img_dir, f"page_{page_num}.png")
                    shutil.copy2(src_img, dest_img)

            # --- Pass 1: Create Pages, Equipment, EquipmentLocations ---
            equipment_count = 0
            created_equipment = {}  # tag -> Equipment object
            all_relationships = []  # collect for two-pass insertion

            for page_info in pages_info:
                page_num = page_info["page_number"]
                image_path = os.path.join(
                    settings.upload_dir, f"doc_{document_id}", "pages", f"page_{page_num}.png"
                )

                page = Page(
                    document_id=document_id,
                    page_number=page_num,
                    ocr_text=page_info.get("ocr_text", ""),
                    processed_text=page_info.get("processed_text", ""),
                    ai_analysis=page_info.get("ai_analysis", ""),
                    ai_equipment_list=json.dumps(page_info.get("ai_equipment_list", [])),
                    image_path=image_path,
                    embedding=page_info.get("embedding"),
                    drawing_type=page_info.get("drawing_type"),
                )
                db.add(page)
                db.flush()

                # Create Equipment and EquipmentLocation records
                for eq_info in page_info.get("equipment", []):
                    tag = eq_info.get("tag", "")
                    if not tag:
                        continue

                    # Dedup by project_id + tag (same as document_processor.py:108-112)
                    if tag in created_equipment:
                        equipment = created_equipment[tag]
                    else:
                        equipment_query = db.query(Equipment).filter(Equipment.tag == tag)
                        if project_id:
                            equipment_query = equipment_query.filter(Equipment.project_id == project_id)
                        equipment = equipment_query.first()

                    if not equipment:
                        equipment = Equipment(
                            tag=tag,
                            equipment_type=eq_info.get("equipment_type", "OTHER"),
                            description=(eq_info.get("context", "") or "")[:500],
                            document_id=document_id,
                            primary_page=page_num,
                            project_id=project_id,
                        )
                        db.add(equipment)
                        db.flush()
                        equipment_count += 1

                    created_equipment[tag] = equipment

                    # Create EquipmentLocation
                    location = EquipmentLocation(
                        equipment_id=equipment.id,
                        page_id=page.id,
                        context_text=(eq_info.get("context", "") or "")[:500],
                    )
                    bbox = eq_info.get("bbox")
                    if bbox and isinstance(bbox, dict):
                        location.x_min = bbox.get("x_min")
                        location.y_min = bbox.get("y_min")
                        location.x_max = bbox.get("x_max")
                        location.y_max = bbox.get("y_max")
                    db.add(location)

                # Collect relationships for pass 2 (equipment may not exist yet)
                for rel_info in page_info.get("relationships", []):
                    all_relationships.append({
                        "source": rel_info.get("source", ""),
                        "target": rel_info.get("target", ""),
                        "type": rel_info.get("type", "CONNECTS_TO"),
                        "confidence": rel_info.get("confidence", 0.7),
                        "page_number": page_num,
                    })

                # Create DetailedConnection records
                for conn in page_info.get("detailed_connections", []):
                    details = conn.get("details", {})
                    wire_info = details.get("wire_info", {})

                    db.add(DetailedConnection(
                        document_id=document_id,
                        page_number=page_num,
                        source_tag=_to_str(conn.get("source", ""), 100),
                        target_tag=_to_str(conn.get("target", ""), 100),
                        category=_to_str(conn.get("category", "UNKNOWN"), 50),
                        connection_type=_to_str(conn.get("connection_type", ""), 50),
                        voltage=_to_str(details.get("voltage"), 50),
                        breaker=_to_str(details.get("breaker"), 100),
                        wire_size=_to_str(wire_info.get("size") if isinstance(wire_info, dict) else None, 50),
                        wire_numbers=json.dumps(wire_info.get("wire_numbers", [])) if isinstance(wire_info, dict) else None,
                        load=_to_str(details.get("load"), 100),
                        signal_type=_to_str(details.get("signal_type"), 50),
                        io_type=_to_str(conn.get("connection_type") if conn.get("category") == "CONTROL" else None, 20),
                        point_name=_to_str(details.get("point_name"), 100),
                        function=_to_str(details.get("function")),
                        medium=_to_str(details.get("medium"), 100),
                        pipe_size=_to_str(details.get("size"), 50),
                        pipe_spec=_to_str(details.get("spec"), 100),
                        inline_devices=json.dumps(details.get("inline_devices", [])) if details.get("inline_devices") else None,
                        details_json=json.dumps(details),
                        confidence=0.7,
                    ))

            # --- Pass 2: Create EquipmentRelationships (all equipment now exists) ---
            relationship_count = 0
            for rel in all_relationships:
                source = created_equipment.get(rel["source"])
                target = created_equipment.get(rel["target"])
                if not source:
                    source = db.query(Equipment).filter(Equipment.tag == rel["source"]).first()
                if not target:
                    target = db.query(Equipment).filter(Equipment.tag == rel["target"]).first()

                if source and target:
                    existing = db.query(EquipmentRelationship).filter(
                        EquipmentRelationship.source_id == source.id,
                        EquipmentRelationship.target_id == target.id,
                        EquipmentRelationship.relationship_type == rel["type"],
                    ).first()

                    if not existing:
                        db.add(EquipmentRelationship(
                            source_id=source.id,
                            target_id=target.id,
                            relationship_type=rel["type"],
                            document_id=document_id,
                            page_number=rel["page_number"],
                            confidence=rel["confidence"],
                        ))
                        relationship_count += 1

            db.commit()

            return ImportResponse(
                document_id=document_id,
                original_filename=doc_info.get("original_filename", "unknown"),
                page_count=len(pages_info),
                equipment_count=equipment_count,
                relationship_count=relationship_count,
                message="Bundle imported successfully. Document is ready for search.",
            )

        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            # Clean up files on failure
            if 'dest_file_path' in locals() and os.path.exists(dest_file_path):
                os.remove(dest_file_path)
            if 'document_id' in locals():
                doc_dir = os.path.join(settings.upload_dir, f"doc_{document_id}")
                if os.path.exists(doc_dir):
                    shutil.rmtree(doc_dir)
            logger.error(f"Import failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Import failed. Check server logs for details.")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/project/{project_id}", response_model=List[DocumentResponse])
async def list_project_documents(
    project_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all documents in a specific project"""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = db.query(Document).filter(
        Document.project_id == project_id
    ).offset(skip).limit(limit).all()
    return documents


@router.get("/unassigned", response_model=List[DocumentResponse])
async def list_unassigned_documents(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all documents not assigned to any project"""
    documents = db.query(Document).filter(
        Document.project_id.is_(None)
    ).offset(skip).limit(limit).all()
    return documents


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all uploaded documents"""
    documents = db.query(Document).offset(skip).limit(limit).all()
    return documents


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document details"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    equipment_count = len(document.equipment)

    pages = [{"id": p.id, "page_number": p.page_number, "equipment_count": len(p.equipment_locations)}
             for p in document.pages]

    return DocumentDetail(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        title=document.title,
        drawing_number=document.drawing_number,
        revision=document.revision,
        system=document.system,
        area=document.area,
        file_size=document.file_size,
        page_count=document.page_count,
        upload_date=document.upload_date,
        processed=document.processed,
        equipment_count=equipment_count,
        pages=pages
    )


@router.delete("/{document_id}")
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and all related data"""
    from app.models.database import EquipmentLocation, EquipmentRelationship

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        # Delete relationships first
        db.query(EquipmentRelationship).filter(
            EquipmentRelationship.document_id == document_id
        ).delete()

        # Delete equipment locations for pages in this document
        page_ids = [p.id for p in document.pages]
        if page_ids:
            db.query(EquipmentLocation).filter(
                EquipmentLocation.page_id.in_(page_ids)
            ).delete(synchronize_session=False)

        # Delete equipment that belongs only to this document
        db.query(Equipment).filter(Equipment.document_id == document_id).delete()

        # Delete pages (cascade should handle this, but be explicit)
        db.query(Page).filter(Page.document_id == document_id).delete()

        # Delete files
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        doc_dir = os.path.join(settings.upload_dir, f"doc_{document_id}")
        if os.path.exists(doc_dir):
            shutil.rmtree(doc_dir)

        # Finally delete the document
        db.delete(document)
        db.commit()

        return {"message": f"Document {document_id} deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.patch("/{document_id}/project", response_model=DocumentResponse)
async def assign_document_to_project(
    document_id: int,
    data: DocumentProjectAssign,
    db: Session = Depends(get_db)
):
    """Assign or reassign a document to a project"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # If project_id is provided, verify the project exists
    if data.project_id is not None:
        project = db.query(Project).filter(Project.id == data.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    # Update the document's project
    document.project_id = data.project_id

    # Also update project_id on all equipment associated with this document
    db.query(Equipment).filter(Equipment.document_id == document_id).update(
        {Equipment.project_id: data.project_id}
    )

    db.commit()
    db.refresh(document)

    return document


# Bulk operation schemas
from pydantic import BaseModel
from typing import List as PyList

class BulkAssignRequest(BaseModel):
    document_ids: PyList[int]
    project_id: Optional[int]  # None to unassign


class BulkDeleteRequest(BaseModel):
    document_ids: PyList[int]


class BulkOperationResponse(BaseModel):
    success_count: int
    failed_count: int
    failed_ids: PyList[int]
    message: str


@router.post("/bulk/assign", response_model=BulkOperationResponse)
async def bulk_assign_documents(
    data: BulkAssignRequest,
    db: Session = Depends(get_db)
):
    """Assign multiple documents to a project at once"""
    if not data.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    # Verify project exists if assigning
    if data.project_id is not None:
        project = db.query(Project).filter(Project.id == data.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    success_count = 0
    failed_ids = []

    for doc_id in data.document_ids:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if document:
            document.project_id = data.project_id
            # Update equipment as well
            db.query(Equipment).filter(Equipment.document_id == doc_id).update(
                {Equipment.project_id: data.project_id}
            )
            success_count += 1
        else:
            failed_ids.append(doc_id)

    db.commit()

    action = f"assigned to project {data.project_id}" if data.project_id else "unassigned from project"
    return BulkOperationResponse(
        success_count=success_count,
        failed_count=len(failed_ids),
        failed_ids=failed_ids,
        message=f"{success_count} documents {action}"
    )


@router.post("/bulk/delete", response_model=BulkOperationResponse)
async def bulk_delete_documents(
    data: BulkDeleteRequest,
    db: Session = Depends(get_db)
):
    """Delete multiple documents at once"""
    from app.models.database import EquipmentLocation, EquipmentRelationship

    if not data.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    success_count = 0
    failed_ids = []

    for doc_id in data.document_ids:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if not document:
            failed_ids.append(doc_id)
            continue

        try:
            # Delete relationships first
            db.query(EquipmentRelationship).filter(
                EquipmentRelationship.document_id == doc_id
            ).delete()

            # Delete equipment locations for pages in this document
            page_ids = [p.id for p in document.pages]
            if page_ids:
                db.query(EquipmentLocation).filter(
                    EquipmentLocation.page_id.in_(page_ids)
                ).delete(synchronize_session=False)

            # Delete equipment that belongs only to this document
            db.query(Equipment).filter(Equipment.document_id == doc_id).delete()

            # Delete pages
            db.query(Page).filter(Page.document_id == doc_id).delete()

            # Delete files
            if os.path.exists(document.file_path):
                os.remove(document.file_path)

            doc_dir = os.path.join(settings.upload_dir, f"doc_{doc_id}")
            if os.path.exists(doc_dir):
                shutil.rmtree(doc_dir)

            # Delete the document
            db.delete(document)
            success_count += 1

        except Exception as e:
            failed_ids.append(doc_id)

    db.commit()

    return BulkOperationResponse(
        success_count=success_count,
        failed_count=len(failed_ids),
        failed_ids=failed_ids,
        message=f"{success_count} documents deleted successfully"
    )


@router.post("/bulk/reprocess", response_model=BulkOperationResponse)
async def bulk_reprocess_documents(
    data: BulkDeleteRequest,  # Reuse schema, just needs document_ids
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Reprocess multiple documents at once"""
    if not data.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    success_count = 0
    failed_ids = []

    for doc_id in data.document_ids:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if not document:
            failed_ids.append(doc_id)
            continue

        # Reset processing state
        document.processed = 0
        document.pages_processed = 0
        document.processing_error = None
        document.page_count = None

        # Clear existing pages and related data
        db.query(Page).filter(Page.document_id == doc_id).delete()
        db.query(Equipment).filter(Equipment.document_id == doc_id).delete()

        # Queue for processing
        background_tasks.add_task(process_document_task, doc_id)
        success_count += 1

    db.commit()

    return BulkOperationResponse(
        success_count=success_count,
        failed_count=len(failed_ids),
        failed_ids=failed_ids,
        message=f"{success_count} documents queued for reprocessing"
    )


@router.post("/{document_id}/retry")
async def retry_processing(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Retry processing a failed or stuck document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Reset processing state
    document.processed = 0
    document.pages_processed = 0
    document.processing_error = None
    document.page_count = None

    # Clear existing pages and related data
    db.query(Page).filter(Page.document_id == document_id).delete()
    db.query(Equipment).filter(Equipment.document_id == document_id).delete()
    db.commit()

    # Start processing again
    background_tasks.add_task(process_document_task, document.id)

    return {"message": f"Processing restarted for document {document_id}"}


@router.get("/status/stuck", response_model=List[DocumentResponse])
async def list_stuck_documents(
    db: Session = Depends(get_db),
    include_failed: bool = Query(default=True, description="Include failed documents (processed=-1)"),
    stuck_threshold_minutes: int = Query(default=30, description="Minutes after which processing is considered stuck")
):
    """List documents stuck in processing or failed state.

    A document is considered stuck if:
    - It has processed=1 (processing) for longer than stuck_threshold_minutes
    - Or it has processed=-1 (failed) if include_failed is True
    """
    from datetime import datetime, timedelta

    stuck_threshold = datetime.utcnow() - timedelta(minutes=stuck_threshold_minutes)

    query = db.query(Document)

    if include_failed:
        # Stuck (processing too long) OR failed
        documents = query.filter(
            ((Document.processed == 1) & (Document.upload_date < stuck_threshold)) |
            (Document.processed == -1)
        ).all()
    else:
        # Only stuck (processing too long)
        documents = query.filter(
            (Document.processed == 1) & (Document.upload_date < stuck_threshold)
        ).all()

    return documents


@router.post("/status/recover-all")
async def recover_all_stuck_documents(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    include_failed: bool = Query(default=True, description="Include failed documents"),
    stuck_threshold_minutes: int = Query(default=30, description="Minutes threshold for stuck detection")
):
    """Recover all stuck and optionally failed documents by resetting and reprocessing them.

    This endpoint:
    1. Finds all documents stuck in processing or failed state
    2. Resets their state to pending
    3. Clears partial processing data
    4. Restarts processing for each

    Returns the count and IDs of documents being recovered.
    """
    from datetime import datetime, timedelta

    stuck_threshold = datetime.utcnow() - timedelta(minutes=stuck_threshold_minutes)

    query = db.query(Document)

    if include_failed:
        documents = query.filter(
            ((Document.processed == 1) & (Document.upload_date < stuck_threshold)) |
            (Document.processed == -1)
        ).all()
    else:
        documents = query.filter(
            (Document.processed == 1) & (Document.upload_date < stuck_threshold)
        ).all()

    if not documents:
        return {
            "message": "No stuck or failed documents found",
            "recovered_count": 0,
            "document_ids": []
        }

    recovered_ids = []

    for document in documents:
        # Reset processing state
        document.processed = 0
        document.pages_processed = 0
        document.processing_error = None
        document.page_count = None

        # Clear existing pages and related data
        db.query(Page).filter(Page.document_id == document.id).delete()
        db.query(Equipment).filter(Equipment.document_id == document.id).delete()

        recovered_ids.append(document.id)

    db.commit()

    # Start processing for all recovered documents
    for doc_id in recovered_ids:
        background_tasks.add_task(process_document_task, doc_id)

    return {
        "message": f"Recovery initiated for {len(recovered_ids)} documents",
        "recovered_count": len(recovered_ids),
        "document_ids": recovered_ids
    }


@router.get("/status/summary")
async def get_processing_status_summary(db: Session = Depends(get_db)):
    """Get a summary of document processing status.

    Returns counts by processing state:
    - pending (0): Waiting to be processed
    - processing (1): Currently being processed
    - completed (2): Successfully processed
    - failed (-1): Processing failed
    """
    from sqlalchemy import func

    status_counts = db.query(
        Document.processed,
        func.count(Document.id)
    ).group_by(Document.processed).all()

    # Map to readable names
    status_map = {
        0: "pending",
        1: "processing",
        2: "completed",
        -1: "failed"
    }

    summary = {
        "pending": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "total": 0
    }

    for status, count in status_counts:
        status_name = status_map.get(status, f"unknown_{status}")
        if status_name in summary:
            summary[status_name] = count
        summary["total"] += count

    return summary


@router.get("/{document_id}/page/{page_number}/image")
async def get_page_image(document_id: int, page_number: int, db: Session = Depends(get_db)):
    """Get page image for viewing"""
    image_path = os.path.join(settings.upload_dir, f"doc_{document_id}", "pages", f"page_{page_number}.png")

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Page image not found")

    return FileResponse(image_path, media_type="image/png")


@router.get("/{document_id}/page/{page_number}/thumbnail")
async def get_page_thumbnail(
    document_id: int,
    page_number: int,
    width: int = Query(default=200, ge=50, le=400),
    db: Session = Depends(get_db)
):
    """Get a thumbnail of a page for preview cards"""
    image_path = os.path.join(settings.upload_dir, f"doc_{document_id}", "pages", f"page_{page_number}.png")

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Page image not found")

    # Create thumbnail
    with Image.open(image_path) as img:
        # Calculate height maintaining aspect ratio
        aspect_ratio = img.height / img.width
        height = int(width * aspect_ratio)

        img.thumbnail((width, height), Image.Resampling.LANCZOS)

        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)

    return StreamingResponse(img_bytes, media_type="image/png")


@router.get("/{document_id}/pdf")
async def get_document_pdf(document_id: int, db: Session = Depends(get_db)):
    """Get the original PDF file for inline viewing (not download)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    # Use headers to display inline instead of download
    return FileResponse(
        document.file_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline",
            "X-Frame-Options": "ALLOWALL"
        }
    )


@router.get("/{document_id}/page/{page_number}/equipment")
async def get_page_equipment(document_id: int, page_number: int, db: Session = Depends(get_db)):
    """Get all equipment on a specific page with their locations"""
    from app.models.database import EquipmentLocation

    page = db.query(Page).filter(
        Page.document_id == document_id,
        Page.page_number == page_number
    ).first()

    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    equipment_list = []
    for loc in page.equipment_locations:
        equipment_list.append({
            "id": loc.equipment.id,
            "tag": loc.equipment.tag,
            "equipment_type": loc.equipment.equipment_type,
            "context": loc.context_text,
            "bbox": {
                "x_min": loc.x_min,
                "y_min": loc.y_min,
                "x_max": loc.x_max,
                "y_max": loc.y_max
            } if loc.x_min is not None else None
        })

    return {
        "page_number": page_number,
        "document_id": document_id,
        "ai_analysis": page.ai_analysis,
        "equipment": equipment_list
    }


@router.get("/{document_id}/pages")
async def get_document_pages(document_id: int, db: Session = Depends(get_db)):
    """Get all pages for a document with summary info"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()

    return {
        "document_id": document_id,
        "original_filename": document.original_filename,
        "page_count": document.page_count,
        "pages": [
            {
                "page_number": p.page_number,
                "equipment_count": len(p.equipment_locations),
                "ai_analysis": p.ai_analysis[:200] if p.ai_analysis else None
            }
            for p in pages
        ]
    }
