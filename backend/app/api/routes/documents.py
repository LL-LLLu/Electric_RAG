import os
import shutil
import uuid
import io
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from PIL import Image

from app.db.session import get_db, SessionLocal
from app.models.database import Document, Page, Equipment, Project
from app.models.schemas import DocumentResponse, DocumentDetail, UploadResponse
from app.services.document_processor import document_processor
from app.config import settings

router = APIRouter()


def process_document_task(document_id: int):
    """Background task to process document"""
    db = SessionLocal()
    try:
        document_processor.process_document(db, document_id)
    finally:
        db.close()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a new electrical drawing PDF"""

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_id = str(uuid.uuid4())
    filename = f"{file_id}.pdf"
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
    """Upload a new electrical drawing PDF to a specific project"""

    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_id = str(uuid.uuid4())
    filename = f"{file_id}.pdf"
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
