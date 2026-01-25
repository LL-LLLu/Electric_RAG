import os
import json
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.database import Project, Document, Equipment, Conversation, Page
from app.models.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetail, ProjectStats
)
from app.config import settings

router = APIRouter()


@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project"""
    db_project = Project(
        name=project.name,
        description=project.description,
        system_type=project.system_type,
        facility_name=project.facility_name,
        status=project.status,
        notes=project.notes,
        tags=json.dumps(project.tags) if project.tags else "[]"
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    # Parse tags back for response
    db_project.tags = json.loads(db_project.tags) if db_project.tags else []
    return db_project


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all projects"""
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    projects = query.order_by(Project.updated_at.desc()).offset(skip).limit(limit).all()

    # Parse tags for each project
    for p in projects:
        p.tags = json.loads(p.tags) if p.tags else []
    return projects


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get project details with stats"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Calculate stats
    doc_count = db.query(func.count(Document.id)).filter(Document.project_id == project_id).scalar()
    equip_count = db.query(func.count(Equipment.id)).filter(Equipment.project_id == project_id).scalar()
    conv_count = db.query(func.count(Conversation.id)).filter(Conversation.project_id == project_id).scalar()
    page_count = db.query(func.count(Page.id)).join(Document).filter(Document.project_id == project_id).scalar()

    project.tags = json.loads(project.tags) if project.tags else []

    return ProjectDetail(
        id=project.id,
        name=project.name,
        description=project.description,
        system_type=project.system_type,
        facility_name=project.facility_name,
        status=project.status,
        cover_image_path=project.cover_image_path,
        notes=project.notes,
        tags=project.tags,
        created_at=project.created_at,
        updated_at=project.updated_at,
        stats=ProjectStats(
            document_count=doc_count or 0,
            equipment_count=equip_count or 0,
            conversation_count=conv_count or 0,
            page_count=page_count or 0
        )
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, update: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = update.model_dump(exclude_unset=True)
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"])

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    project.tags = json.loads(project.tags) if project.tags else []
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project and all its data"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete project directory if exists
    try:
        project_dir = os.path.join(settings.upload_dir, f"project_{project_id}")
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)

        # Delete cover image if exists
        if project.cover_image_path and os.path.exists(project.cover_image_path):
            os.remove(project.cover_image_path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project files: {str(e)}")

    # Cascade delete will handle documents, equipment, conversations
    db.delete(project)
    db.commit()

    return {"message": f"Project {project_id} deleted successfully"}


@router.post("/{project_id}/cover-image")
async def upload_cover_image(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a cover image for the project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")

    # Create project images directory
    images_dir = os.path.join(settings.upload_dir, "project_images")
    os.makedirs(images_dir, exist_ok=True)

    # Delete old cover image if exists
    if project.cover_image_path and os.path.exists(project.cover_image_path):
        os.remove(project.cover_image_path)

    # Save new image
    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "jpg"
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file extension")

    filename = f"project_{project_id}_cover.{ext}"
    file_path = os.path.join(images_dir, filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save cover image: {str(e)}")

    project.cover_image_path = file_path
    db.commit()

    return {"message": "Cover image uploaded successfully", "path": file_path}
