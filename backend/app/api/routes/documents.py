import os
import shutil
import uuid
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.database import Document
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
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    doc_dir = os.path.join(settings.upload_dir, f"doc_{document_id}")
    if os.path.exists(doc_dir):
        shutil.rmtree(doc_dir)

    db.delete(document)
    db.commit()

    return {"message": f"Document {document_id} deleted successfully"}


@router.get("/{document_id}/page/{page_number}/image")
async def get_page_image(document_id: int, page_number: int, db: Session = Depends(get_db)):
    """Get page image for viewing"""
    image_path = os.path.join(settings.upload_dir, f"doc_{document_id}", "pages", f"page_{page_number}.png")

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Page image not found")

    return FileResponse(image_path, media_type="image/png")
