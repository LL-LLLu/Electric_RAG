import os
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import SupplementaryDocument, EquipmentAlias, EquipmentProfile, Equipment
from app.models.schemas import (
    SupplementaryDocumentResponse, EquipmentAliasCreate, EquipmentAliasResponse,
    EquipmentProfileResponse, ContentCategory
)
from app.db.session import get_db, SessionLocal
from app.config import settings
from app.services.supplementary_processor import supplementary_processor

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.docx'}

# Maximum file size per design spec
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def get_document_type(filename: str) -> str:
    """Determine document type from filename"""
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.xlsx', '.xls', '.csv']:
        return 'EXCEL'
    elif ext == '.docx':
        return 'WORD'
    raise ValueError(f"Unsupported file type: {ext}")


@router.post("/projects/{project_id}/supplementary", response_model=SupplementaryDocumentResponse)
async def upload_supplementary(
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    content_category: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a supplementary document (Excel or Word)"""
    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Determine document type
    try:
        document_type = get_document_type(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{ext}"

    # Create supplementary subdirectory if needed
    supp_dir = os.path.join(settings.upload_dir, "supplementary")
    os.makedirs(supp_dir, exist_ok=True)

    file_path = os.path.join(supp_dir, unique_filename)

    # Read and validate file size
    try:
        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)} MB"
            )

        with open(file_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")

    # Create database record (with cleanup on failure)
    try:
        document = SupplementaryDocument(
            project_id=project_id,
            filename=unique_filename,
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
    except Exception as e:
        # Clean up file if database operation failed
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                logger.warning(f"Failed to clean up orphaned file: {file_path}")
        logger.error(f"Failed to create document record: {e}")
        raise HTTPException(status_code=500, detail="Failed to create document record")

    # Process in background
    background_tasks.add_task(process_document_task, document.id)

    return document


def process_document_task(document_id: int):
    """Background task to process uploaded document"""
    db = SessionLocal()
    try:
        document = db.query(SupplementaryDocument).filter(
            SupplementaryDocument.id == document_id
        ).first()
        if document:
            supplementary_processor.process_document(db, document)
    finally:
        db.close()


@router.get("/projects/{project_id}/supplementary", response_model=List[SupplementaryDocumentResponse])
async def list_supplementary(project_id: int, db: Session = Depends(get_db)):
    """List all supplementary documents for a project"""
    documents = db.query(SupplementaryDocument).filter(
        SupplementaryDocument.project_id == project_id
    ).order_by(SupplementaryDocument.created_at.desc()).all()
    return documents


@router.get("/supplementary/{document_id}", response_model=SupplementaryDocumentResponse)
async def get_supplementary(document_id: int, db: Session = Depends(get_db)):
    """Get a specific supplementary document"""
    document = db.query(SupplementaryDocument).filter(
        SupplementaryDocument.id == document_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/supplementary/{document_id}")
async def delete_supplementary(document_id: int, db: Session = Depends(get_db)):
    """Delete a supplementary document"""
    document = db.query(SupplementaryDocument).filter(
        SupplementaryDocument.id == document_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file from disk
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {document.file_path}: {e}")

    # Delete from database (cascades to chunks and equipment_data)
    db.delete(document)
    db.commit()

    return {"message": "Document deleted successfully"}


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

    # Reset status
    document.processed = 0
    document.processing_error = None
    db.commit()

    # Reprocess in background
    background_tasks.add_task(process_document_task, document_id)

    return {"message": "Reprocessing started"}


def get_equipment_by_tag(tag: str, db: Session) -> Equipment:
    """Get equipment by tag with case-insensitive lookup"""
    equipment = db.query(Equipment).filter(
        Equipment.tag.ilike(tag)
    ).first()
    if not equipment:
        raise HTTPException(status_code=404, detail=f"Equipment '{tag}' not found")
    return equipment


@router.get("/equipment/{tag}/profile", response_model=EquipmentProfileResponse)
async def get_equipment_profile(tag: str, db: Session = Depends(get_db)):
    """Get the aggregated profile for an equipment tag"""
    equipment = get_equipment_by_tag(tag, db)

    profile = db.query(EquipmentProfile).filter(
        EquipmentProfile.equipment_id == equipment.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile found for equipment '{tag}'")

    return profile


@router.get("/equipment/{tag}/aliases", response_model=List[EquipmentAliasResponse])
async def get_equipment_aliases(tag: str, db: Session = Depends(get_db)):
    """Get all aliases for an equipment tag"""
    equipment = get_equipment_by_tag(tag, db)

    aliases = db.query(EquipmentAlias).filter(
        EquipmentAlias.equipment_id == equipment.id
    ).all()
    return aliases


@router.post("/equipment/{tag}/aliases", response_model=EquipmentAliasResponse)
async def add_equipment_alias(
    tag: str,
    alias_data: EquipmentAliasCreate,
    db: Session = Depends(get_db)
):
    """Add a manual alias for an equipment tag"""
    equipment = get_equipment_by_tag(tag, db)

    # Check if alias already exists
    existing = db.query(EquipmentAlias).filter(
        EquipmentAlias.equipment_id == equipment.id,
        EquipmentAlias.alias.ilike(alias_data.alias)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Alias already exists for this equipment")

    alias = EquipmentAlias(
        equipment_id=equipment.id,
        alias=alias_data.alias,
        source=alias_data.source or "manual",
        confidence=alias_data.confidence or 1.0
    )
    db.add(alias)
    db.commit()
    db.refresh(alias)

    return alias
