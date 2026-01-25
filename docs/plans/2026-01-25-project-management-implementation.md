# Project-Based File Management System - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Electric_RAG into a project-based file management system with chat interface, persistent conversations, and source reference previews.

**Architecture:** Add a Project layer above Documents. Projects contain documents, equipment, and conversations. Search can be scoped to a project or global. Chat interface with 20/80 split shows AI responses with source cards that link to highlighted PDF regions.

**Tech Stack:** FastAPI (backend), Vue 3 + Pinia (frontend), PostgreSQL with pgvector, SQLAlchemy ORM, Axios

**Design Document:** `docs/plans/2026-01-25-project-management-design.md`

---

## Phase 1: Database & Backend Foundation

### Task 1.1: Create Project Database Model

**Files:**
- Modify: `backend/app/models/database.py`

**Step 1: Add Project model to database.py**

Add after the `Base = declarative_base()` line and before `Document` class:

```python
class Project(Base):
    """Represents a project containing documents"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    system_type = Column(String(100))  # electrical, mechanical, HVAC
    facility_name = Column(String(255))
    status = Column(String(50), default="active")  # active, archived, completed
    cover_image_path = Column(String(500))
    notes = Column(Text)
    tags = Column(Text)  # JSON array stored as text
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    equipment = relationship("Equipment", back_populates="project")
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
```

**Step 2: Add project_id to Document model**

Add to the Document class after line 13 (`id` column):

```python
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    project = relationship("Project", back_populates="documents")
```

**Step 3: Add project_id to Equipment model**

Add to the Equipment class after line 59 (`id` column):

```python
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    project = relationship("Project", back_populates="equipment")
```

Remove the `unique=True` from the `tag` column (line 60) since tags are now unique per project:

```python
    tag = Column(String(100), nullable=False, index=True)  # Remove unique=True
```

Add table args for project-scoped unique constraint at the end of Equipment class:

```python
    __table_args__ = (
        Index('idx_equipment_project_tag', 'project_id', 'tag', unique=True),
    )
```

**Step 4: Commit**

```bash
git add backend/app/models/database.py
git commit -m "feat(db): add Project model and project_id to Document/Equipment"
```

---

### Task 1.2: Create Conversation and Message Models

**Files:**
- Modify: `backend/app/models/database.py`

**Step 1: Add Conversation model after Project class**

```python
class Conversation(Base):
    """Represents a chat conversation within a project"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_conversation_project', 'project_id'),
    )


class Message(Base):
    """Represents a message in a conversation"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(Text)  # JSON array of source references
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index('idx_message_conversation', 'conversation_id'),
    )
```

**Step 2: Commit**

```bash
git add backend/app/models/database.py
git commit -m "feat(db): add Conversation and Message models"
```

---

### Task 1.3: Create Pydantic Schemas for Projects

**Files:**
- Modify: `backend/app/models/schemas.py`

**Step 1: Add Project schemas after the imports section**

```python
# Project Schemas
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_type: Optional[str] = None
    facility_name: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    tags: Optional[List[str]] = []


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_type: Optional[str] = None
    facility_name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class ProjectResponse(ProjectBase):
    id: int
    cover_image_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectStats(BaseModel):
    document_count: int = 0
    equipment_count: int = 0
    conversation_count: int = 0
    page_count: int = 0


class ProjectDetail(ProjectResponse):
    stats: ProjectStats
```

**Step 2: Commit**

```bash
git add backend/app/models/schemas.py
git commit -m "feat(schemas): add Project Pydantic schemas"
```

---

### Task 1.4: Create Pydantic Schemas for Conversations

**Files:**
- Modify: `backend/app/models/schemas.py`

**Step 1: Add Conversation and Message schemas**

```python
# Conversation Schemas
class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    id: int
    project_id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceReference(BaseModel):
    document_id: int
    document_name: str
    page_number: int
    snippet: Optional[str] = None
    bbox: Optional[dict] = None
    equipment_tag: Optional[str] = None


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[List[SourceReference]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationDetail(ConversationResponse):
    messages: List[MessageResponse] = []
```

**Step 2: Commit**

```bash
git add backend/app/models/schemas.py
git commit -m "feat(schemas): add Conversation and Message Pydantic schemas"
```

---

### Task 1.5: Create Database Migration Script

**Files:**
- Create: `scripts/migrate_to_projects.sql`

**Step 1: Create migration script**

```sql
-- Migration script: Add project support to Electric_RAG
-- Run with: psql -d electrical_rag -f scripts/migrate_to_projects.sql

-- 1. Create projects table
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_type VARCHAR(100),
    facility_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    cover_image_path VARCHAR(500),
    notes TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Create conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_project ON conversations(project_id);

-- 3. Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_conversation ON messages(conversation_id);

-- 4. Add project_id to documents (nullable first for migration)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE;

-- 5. Add project_id to equipment (nullable first for migration)
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE;

-- 6. Create default project for existing data
INSERT INTO projects (name, description, status, created_at, updated_at)
SELECT 'Default Project', 'Auto-created project for existing documents', 'active', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE name = 'Default Project');

-- 7. Migrate existing documents to default project
UPDATE documents
SET project_id = (SELECT id FROM projects WHERE name = 'Default Project' LIMIT 1)
WHERE project_id IS NULL;

-- 8. Migrate existing equipment to default project
UPDATE equipment
SET project_id = (SELECT id FROM projects WHERE name = 'Default Project' LIMIT 1)
WHERE project_id IS NULL;

-- 9. Create indexes
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_equipment_project_id ON equipment(project_id);

-- 10. Drop old unique constraint on equipment.tag and add project-scoped one
-- First check if the old constraint exists and drop it
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'equipment_tag_key') THEN
        ALTER TABLE equipment DROP CONSTRAINT equipment_tag_key;
    END IF;
END $$;

-- Create new project-scoped unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_equipment_project_tag ON equipment(project_id, tag);

-- Done!
SELECT 'Migration complete. Default project created with ID: ' || id FROM projects WHERE name = 'Default Project';
```

**Step 2: Commit**

```bash
git add scripts/migrate_to_projects.sql
git commit -m "feat(db): add migration script for project support"
```

---

### Task 1.6: Create Projects API Router

**Files:**
- Create: `backend/app/api/routes/projects.py`

**Step 1: Create the projects router**

```python
import os
import json
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
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
    project_dir = os.path.join(settings.upload_dir, f"project_{project_id}")
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)

    # Delete cover image if exists
    if project.cover_image_path and os.path.exists(project.cover_image_path):
        os.remove(project.cover_image_path)

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
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"project_{project_id}_cover.{ext}"
    file_path = os.path.join(images_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    project.cover_image_path = file_path
    db.commit()

    return {"message": "Cover image uploaded successfully", "path": file_path}
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/projects.py
git commit -m "feat(api): add Projects CRUD endpoints"
```

---

### Task 1.7: Register Projects Router in Main App

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Import and register the projects router**

Find the router imports section and add:

```python
from app.api.routes.projects import router as projects_router
```

Find where routers are included (e.g., `app.include_router(...)`) and add:

```python
app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
```

**Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(api): register projects router in main app"
```

---

### Task 1.8: Update Document Upload for Project Scope

**Files:**
- Modify: `backend/app/api/routes/documents.py`

**Step 1: Add project-scoped upload endpoint**

Add a new endpoint for uploading to a specific project. Add after the existing imports:

```python
from app.models.database import Project
```

Add new endpoint (keep the old one for backward compatibility):

```python
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
        project_id=project_id  # Associate with project
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
```

**Step 2: Add project-scoped list endpoint**

```python
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
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/documents.py
git commit -m "feat(api): add project-scoped document upload and list endpoints"
```

---

### Task 1.9: Update Document Processor for Project Scope

**Files:**
- Modify: `backend/app/services/document_processor.py`

**Step 1: Update equipment creation to include project_id**

Find where Equipment objects are created (search for `Equipment(`) and add project_id:

```python
# When creating equipment, get project_id from document
project_id = document.project_id

equipment = Equipment(
    tag=tag,
    equipment_type=equipment_type,
    description=description,
    document_id=document.id,
    primary_page=page_number,
    project_id=project_id  # Add this line
)
```

**Step 2: Update any equipment queries to be project-scoped**

When checking for existing equipment (to avoid duplicates), filter by project:

```python
# Instead of:
existing = db.query(Equipment).filter(Equipment.tag == tag).first()

# Use:
existing = db.query(Equipment).filter(
    Equipment.tag == tag,
    Equipment.project_id == project_id
).first()
```

**Step 3: Commit**

```bash
git add backend/app/services/document_processor.py
git commit -m "feat(processor): update document processor for project-scoped equipment"
```

---

### Task 1.10: Add Page Thumbnail Endpoint

**Files:**
- Modify: `backend/app/api/routes/documents.py`

**Step 1: Add thumbnail endpoint for source previews**

```python
from PIL import Image
import io

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

    from fastapi.responses import StreamingResponse
    return StreamingResponse(img_bytes, media_type="image/png")
```

**Step 2: Add Pillow to requirements if not present**

Check `backend/requirements.txt` for `Pillow`. If not present, add it.

**Step 3: Commit**

```bash
git add backend/app/api/routes/documents.py backend/requirements.txt
git commit -m "feat(api): add page thumbnail endpoint for source previews"
```

---

## Phase 2: Project Management Frontend

### Task 2.1: Create Project TypeScript Types

**Files:**
- Modify: `frontend-vue/src/types/index.ts`

**Step 1: Add Project types**

```typescript
// Project types
export interface Project {
  id: number
  name: string
  description: string | null
  system_type: string | null
  facility_name: string | null
  status: string
  cover_image_path: string | null
  notes: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ProjectStats {
  document_count: number
  equipment_count: number
  conversation_count: number
  page_count: number
}

export interface ProjectDetail extends Project {
  stats: ProjectStats
}

export interface ProjectCreate {
  name: string
  description?: string
  system_type?: string
  facility_name?: string
  status?: string
  notes?: string
  tags?: string[]
}

export interface ProjectUpdate {
  name?: string
  description?: string
  system_type?: string
  facility_name?: string
  status?: string
  notes?: string
  tags?: string[]
}

// Conversation types
export interface Conversation {
  id: number
  project_id: number
  title: string | null
  created_at: string
  updated_at: string
}

export interface SourceReference {
  document_id: number
  document_name: string
  page_number: number
  snippet: string | null
  bbox: { x_min: number; y_min: number; x_max: number; y_max: number } | null
  equipment_tag: string | null
}

export interface Message {
  id: number
  conversation_id: number
  role: 'user' | 'assistant'
  content: string
  sources: SourceReference[] | null
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}
```

**Step 2: Commit**

```bash
git add frontend-vue/src/types/index.ts
git commit -m "feat(types): add Project, Conversation, and Message TypeScript types"
```

---

### Task 2.2: Create Projects API Module

**Files:**
- Create: `frontend-vue/src/api/projects.ts`

**Step 1: Create the API module**

```typescript
import api from './index'
import type { Project, ProjectDetail, ProjectCreate, ProjectUpdate } from '@/types'

export async function list(status?: string): Promise<Project[]> {
  const params: Record<string, string> = {}
  if (status) params.status = status
  const response = await api.get<Project[]>('/api/projects', { params })
  return response.data
}

export async function get(id: number): Promise<ProjectDetail> {
  const response = await api.get<ProjectDetail>(`/api/projects/${id}`)
  return response.data
}

export async function create(data: ProjectCreate): Promise<Project> {
  const response = await api.post<Project>('/api/projects', data)
  return response.data
}

export async function update(id: number, data: ProjectUpdate): Promise<Project> {
  const response = await api.put<Project>(`/api/projects/${id}`, data)
  return response.data
}

export async function deleteProject(id: number): Promise<void> {
  await api.delete(`/api/projects/${id}`)
}

export async function uploadCoverImage(id: number, file: File): Promise<{ path: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<{ message: string; path: string }>(
    `/api/projects/${id}/cover-image`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}

export function getCoverImageUrl(path: string | null): string | null {
  if (!path) return null
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  return `${baseUrl}/uploads/project_images/${path.split('/').pop()}`
}
```

**Step 2: Commit**

```bash
git add frontend-vue/src/api/projects.ts
git commit -m "feat(api): add Projects API module"
```

---

### Task 2.3: Create Projects Pinia Store

**Files:**
- Create: `frontend-vue/src/stores/projects.ts`

**Step 1: Create the store**

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Project, ProjectDetail, ProjectCreate, ProjectUpdate } from '@/types'
import * as projectsApi from '@/api/projects'

export const useProjectsStore = defineStore('projects', () => {
  // State
  const projects = ref<Project[]>([])
  const currentProject = ref<ProjectDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const activeProjects = computed(() =>
    projects.value.filter(p => p.status === 'active')
  )

  const archivedProjects = computed(() =>
    projects.value.filter(p => p.status === 'archived')
  )

  // Actions
  async function fetchProjects(status?: string) {
    loading.value = true
    error.value = null
    try {
      projects.value = await projectsApi.list(status)
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch projects'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchProject(id: number) {
    loading.value = true
    error.value = null
    try {
      currentProject.value = await projectsApi.get(id)
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch project'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createProject(data: ProjectCreate): Promise<Project> {
    loading.value = true
    error.value = null
    try {
      const project = await projectsApi.create(data)
      projects.value.unshift(project)
      return project
    } catch (err: any) {
      error.value = err.message || 'Failed to create project'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateProject(id: number, data: ProjectUpdate) {
    loading.value = true
    error.value = null
    try {
      const updated = await projectsApi.update(id, data)
      const index = projects.value.findIndex(p => p.id === id)
      if (index !== -1) {
        projects.value[index] = updated
      }
      if (currentProject.value?.id === id) {
        currentProject.value = { ...currentProject.value, ...updated }
      }
    } catch (err: any) {
      error.value = err.message || 'Failed to update project'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteProject(id: number) {
    loading.value = true
    error.value = null
    try {
      await projectsApi.deleteProject(id)
      projects.value = projects.value.filter(p => p.id !== id)
      if (currentProject.value?.id === id) {
        currentProject.value = null
      }
    } catch (err: any) {
      error.value = err.message || 'Failed to delete project'
      throw err
    } finally {
      loading.value = false
    }
  }

  function clearCurrentProject() {
    currentProject.value = null
  }

  return {
    // State
    projects,
    currentProject,
    loading,
    error,
    // Getters
    activeProjects,
    archivedProjects,
    // Actions
    fetchProjects,
    fetchProject,
    createProject,
    updateProject,
    deleteProject,
    clearCurrentProject
  }
})
```

**Step 2: Export from stores index**

Modify `frontend-vue/src/stores/index.ts` to export the new store.

**Step 3: Commit**

```bash
git add frontend-vue/src/stores/projects.ts frontend-vue/src/stores/index.ts
git commit -m "feat(store): add Projects Pinia store"
```

---

### Task 2.4: Create Landing Page View

**Files:**
- Create: `frontend-vue/src/views/LandingView.vue`

**Step 1: Create the landing page**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { MagnifyingGlassIcon, PlusIcon, FolderIcon } from '@heroicons/vue/24/outline'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import ProjectCard from '@/components/projects/ProjectCard.vue'
import ProjectForm from '@/components/projects/ProjectForm.vue'

const router = useRouter()
const projectsStore = useProjectsStore()

const globalSearchQuery = ref('')
const showCreateModal = ref(false)

onMounted(async () => {
  await projectsStore.fetchProjects()
})

function handleGlobalSearch() {
  if (globalSearchQuery.value.trim()) {
    router.push({
      name: 'global-search',
      query: { q: globalSearchQuery.value }
    })
  }
}

function handleProjectClick(projectId: number) {
  router.push({ name: 'project-dashboard', params: { projectId } })
}

async function handleProjectCreated() {
  showCreateModal.value = false
  await projectsStore.fetchProjects()
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header with Global Search -->
    <div class="bg-white shadow">
      <div class="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        <div class="flex flex-col items-center space-y-4">
          <h1 class="text-3xl font-bold text-gray-900">Electric RAG</h1>
          <p class="text-gray-500">Search across all your electrical drawings</p>

          <!-- Global Search Bar -->
          <form @submit.prevent="handleGlobalSearch" class="w-full max-w-2xl">
            <div class="relative">
              <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                v-model="globalSearchQuery"
                type="text"
                placeholder="Search across all projects..."
                class="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <button
                type="submit"
                class="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Search
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Projects Section -->
    <div class="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-xl font-semibold text-gray-900">Projects</h2>
        <button
          @click="showCreateModal = true"
          class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <PlusIcon class="h-5 w-5 mr-2" />
          New Project
        </button>
      </div>

      <!-- Loading State -->
      <LoadingSpinner v-if="projectsStore.loading" text="Loading projects..." />

      <!-- Error State -->
      <ErrorAlert
        v-else-if="projectsStore.error"
        :message="projectsStore.error"
        dismissable
        @dismiss="projectsStore.error = null"
      />

      <!-- Empty State -->
      <div
        v-else-if="projectsStore.projects.length === 0"
        class="text-center py-12 bg-white rounded-lg border-2 border-dashed border-gray-300"
      >
        <FolderIcon class="mx-auto h-12 w-12 text-gray-400" />
        <h3 class="mt-2 text-lg font-medium text-gray-900">No projects yet</h3>
        <p class="mt-1 text-gray-500">Get started by creating your first project.</p>
        <button
          @click="showCreateModal = true"
          class="mt-4 inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <PlusIcon class="h-5 w-5 mr-2" />
          Create Project
        </button>
      </div>

      <!-- Projects Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <ProjectCard
          v-for="project in projectsStore.projects"
          :key="project.id"
          :project="project"
          @click="handleProjectClick(project.id)"
        />
      </div>
    </div>

    <!-- Create Project Modal -->
    <ProjectForm
      v-if="showCreateModal"
      @close="showCreateModal = false"
      @created="handleProjectCreated"
    />
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend-vue/src/views/LandingView.vue
git commit -m "feat(views): add Landing page with global search and projects grid"
```

---

### Task 2.5: Create ProjectCard Component

**Files:**
- Create: `frontend-vue/src/components/projects/ProjectCard.vue`

**Step 1: Create the component**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { Project } from '@/types'
import { FolderIcon, DocumentTextIcon, CpuChipIcon, ChatBubbleLeftRightIcon } from '@heroicons/vue/24/outline'
import * as projectsApi from '@/api/projects'

const props = defineProps<{
  project: Project
}>()

const emit = defineEmits<{
  (e: 'click'): void
}>()

const coverImageUrl = computed(() => projectsApi.getCoverImageUrl(props.project.cover_image_path))

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  archived: 'bg-gray-100 text-gray-800',
  completed: 'bg-blue-100 text-blue-800'
}

const formattedDate = computed(() => {
  const date = new Date(props.project.updated_at)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
})
</script>

<template>
  <div
    @click="emit('click')"
    class="bg-white rounded-lg shadow hover:shadow-md transition-shadow cursor-pointer overflow-hidden"
  >
    <!-- Cover Image or Placeholder -->
    <div class="h-32 bg-gradient-to-br from-blue-500 to-blue-600 relative">
      <img
        v-if="coverImageUrl"
        :src="coverImageUrl"
        :alt="project.name"
        class="w-full h-full object-cover"
      />
      <div v-else class="w-full h-full flex items-center justify-center">
        <FolderIcon class="h-16 w-16 text-white/50" />
      </div>

      <!-- Status Badge -->
      <span
        :class="['absolute top-2 right-2 px-2 py-1 text-xs font-medium rounded', statusColors[project.status] || statusColors.active]"
      >
        {{ project.status }}
      </span>
    </div>

    <!-- Content -->
    <div class="p-4">
      <h3 class="text-lg font-semibold text-gray-900 truncate">{{ project.name }}</h3>
      <p v-if="project.description" class="mt-1 text-sm text-gray-500 line-clamp-2">
        {{ project.description }}
      </p>

      <!-- Metadata -->
      <div class="mt-3 flex items-center text-xs text-gray-400 space-x-3">
        <span v-if="project.facility_name">{{ project.facility_name }}</span>
        <span v-if="project.system_type" class="px-2 py-0.5 bg-gray-100 rounded">
          {{ project.system_type }}
        </span>
      </div>

      <!-- Tags -->
      <div v-if="project.tags && project.tags.length > 0" class="mt-2 flex flex-wrap gap-1">
        <span
          v-for="tag in project.tags.slice(0, 3)"
          :key="tag"
          class="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded"
        >
          {{ tag }}
        </span>
        <span v-if="project.tags.length > 3" class="text-xs text-gray-400">
          +{{ project.tags.length - 3 }} more
        </span>
      </div>

      <!-- Footer -->
      <div class="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
        <span>Updated {{ formattedDate }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
```

**Step 2: Commit**

```bash
git add frontend-vue/src/components/projects/ProjectCard.vue
git commit -m "feat(components): add ProjectCard component"
```

---

### Task 2.6: Create ProjectForm Component

**Files:**
- Create: `frontend-vue/src/components/projects/ProjectForm.vue`

**Step 1: Create the modal form**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { XMarkIcon } from '@heroicons/vue/24/outline'
import { useProjectsStore } from '@/stores/projects'
import type { ProjectCreate } from '@/types'

const props = defineProps<{
  project?: ProjectCreate & { id?: number }
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'created'): void
  (e: 'updated'): void
}>()

const projectsStore = useProjectsStore()

const isEditing = computed(() => !!props.project?.id)

const form = ref<ProjectCreate>({
  name: props.project?.name || '',
  description: props.project?.description || '',
  system_type: props.project?.system_type || '',
  facility_name: props.project?.facility_name || '',
  status: props.project?.status || 'active',
  notes: props.project?.notes || '',
  tags: props.project?.tags || []
})

const tagInput = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

const systemTypes = ['Electrical', 'Mechanical', 'HVAC', 'Plumbing', 'Fire Protection', 'Other']
const statusOptions = ['active', 'archived', 'completed']

function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !form.value.tags?.includes(tag)) {
    form.value.tags = [...(form.value.tags || []), tag]
    tagInput.value = ''
  }
}

function removeTag(tag: string) {
  form.value.tags = form.value.tags?.filter(t => t !== tag) || []
}

async function handleSubmit() {
  if (!form.value.name.trim()) {
    error.value = 'Project name is required'
    return
  }

  submitting.value = true
  error.value = null

  try {
    if (isEditing.value && props.project?.id) {
      await projectsStore.updateProject(props.project.id, form.value)
      emit('updated')
    } else {
      await projectsStore.createProject(form.value)
      emit('created')
    }
  } catch (err: any) {
    error.value = err.message || 'Failed to save project'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 overflow-y-auto">
    <!-- Backdrop -->
    <div class="fixed inset-0 bg-black/50" @click="emit('close')"></div>

    <!-- Modal -->
    <div class="relative min-h-screen flex items-center justify-center p-4">
      <div class="relative bg-white rounded-lg shadow-xl w-full max-w-lg">
        <!-- Header -->
        <div class="flex items-center justify-between p-4 border-b">
          <h3 class="text-lg font-semibold text-gray-900">
            {{ isEditing ? 'Edit Project' : 'Create New Project' }}
          </h3>
          <button @click="emit('close')" class="text-gray-400 hover:text-gray-500">
            <XMarkIcon class="h-6 w-6" />
          </button>
        </div>

        <!-- Form -->
        <form @submit.prevent="handleSubmit" class="p-4 space-y-4">
          <!-- Error -->
          <div v-if="error" class="p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {{ error }}
          </div>

          <!-- Name -->
          <div>
            <label class="block text-sm font-medium text-gray-700">Name *</label>
            <input
              v-model="form.name"
              type="text"
              required
              class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              placeholder="Project name"
            />
          </div>

          <!-- Description -->
          <div>
            <label class="block text-sm font-medium text-gray-700">Description</label>
            <textarea
              v-model="form.description"
              rows="3"
              class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              placeholder="Brief description of the project"
            ></textarea>
          </div>

          <!-- System Type & Facility -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700">System Type</label>
              <select
                v-model="form.system_type"
                class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Select type</option>
                <option v-for="type in systemTypes" :key="type" :value="type">{{ type }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700">Facility Name</label>
              <input
                v-model="form.facility_name"
                type="text"
                class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                placeholder="Plant / Building name"
              />
            </div>
          </div>

          <!-- Status -->
          <div>
            <label class="block text-sm font-medium text-gray-700">Status</label>
            <select
              v-model="form.status"
              class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              <option v-for="status in statusOptions" :key="status" :value="status">
                {{ status.charAt(0).toUpperCase() + status.slice(1) }}
              </option>
            </select>
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-sm font-medium text-gray-700">Tags</label>
            <div class="mt-1 flex">
              <input
                v-model="tagInput"
                type="text"
                @keydown.enter.prevent="addTag"
                class="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:ring-blue-500 focus:border-blue-500"
                placeholder="Add a tag"
              />
              <button
                type="button"
                @click="addTag"
                class="px-4 py-2 bg-gray-100 border border-l-0 border-gray-300 rounded-r-md hover:bg-gray-200"
              >
                Add
              </button>
            </div>
            <div v-if="form.tags && form.tags.length > 0" class="mt-2 flex flex-wrap gap-2">
              <span
                v-for="tag in form.tags"
                :key="tag"
                class="inline-flex items-center px-2 py-1 bg-blue-50 text-blue-700 text-sm rounded"
              >
                {{ tag }}
                <button type="button" @click="removeTag(tag)" class="ml-1 text-blue-500 hover:text-blue-700">
                  <XMarkIcon class="h-4 w-4" />
                </button>
              </span>
            </div>
          </div>

          <!-- Notes -->
          <div>
            <label class="block text-sm font-medium text-gray-700">Notes</label>
            <textarea
              v-model="form.notes"
              rows="2"
              class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              placeholder="Additional notes"
            ></textarea>
          </div>

          <!-- Actions -->
          <div class="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              @click="emit('close')"
              class="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="submitting"
              class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {{ submitting ? 'Saving...' : (isEditing ? 'Update' : 'Create') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend-vue/src/components/projects/ProjectForm.vue
git commit -m "feat(components): add ProjectForm modal component"
```

---

### Task 2.7: Update Router with Project Routes

**Files:**
- Modify: `frontend-vue/src/router/index.ts`

**Step 1: Add new routes**

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // Landing page (new home)
  {
    path: '/',
    name: 'landing',
    component: () => import('@/views/LandingView.vue')
  },

  // Global search results
  {
    path: '/search',
    name: 'global-search',
    component: () => import('@/views/GlobalSearchView.vue')
  },

  // Project routes
  {
    path: '/projects/:projectId',
    name: 'project-dashboard',
    component: () => import('@/views/ProjectDashboardView.vue'),
    props: true
  },
  {
    path: '/projects/:projectId/documents',
    name: 'project-documents',
    component: () => import('@/views/ProjectDocumentsView.vue'),
    props: true
  },
  {
    path: '/projects/:projectId/conversations',
    name: 'project-conversations',
    component: () => import('@/views/ProjectConversationsView.vue'),
    props: true
  },
  {
    path: '/projects/:projectId/chat/:conversationId?',
    name: 'project-chat',
    component: () => import('@/views/ProjectChatView.vue'),
    props: true
  },

  // Keep legacy routes for backward compatibility
  {
    path: '/search-legacy',
    name: 'search',
    component: () => import('@/views/SearchView.vue')
  },
  {
    path: '/upload',
    name: 'upload',
    component: () => import('@/views/UploadView.vue')
  },
  {
    path: '/equipment',
    name: 'equipment',
    component: () => import('@/views/EquipmentView.vue')
  },
  {
    path: '/documents',
    name: 'documents',
    component: () => import('@/views/DocumentsView.vue')
  },
  {
    path: '/viewer/:docId?/:pageNum?',
    name: 'viewer',
    component: () => import('@/views/ViewerView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
```

**Step 2: Commit**

```bash
git add frontend-vue/src/router/index.ts
git commit -m "feat(router): add project-based routes"
```

---

### Task 2.8: Create Project Dashboard View

**Files:**
- Create: `frontend-vue/src/views/ProjectDashboardView.vue`

**Step 1: Create the dashboard view**

```vue
<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import {
  DocumentTextIcon,
  CpuChipIcon,
  ChatBubbleLeftRightIcon,
  DocumentDuplicateIcon,
  PencilIcon,
  ArrowLeftIcon,
  PlusIcon
} from '@heroicons/vue/24/outline'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import ProjectForm from '@/components/projects/ProjectForm.vue'

const props = defineProps<{
  projectId: string
}>()

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()

const showEditModal = ref(false)
const loading = ref(true)
const error = ref<string | null>(null)

const projectIdNum = parseInt(props.projectId)

onMounted(async () => {
  await loadProject()
})

watch(() => props.projectId, async () => {
  await loadProject()
})

async function loadProject() {
  loading.value = true
  error.value = null
  try {
    await projectsStore.fetchProject(projectIdNum)
  } catch (err: any) {
    error.value = err.message || 'Failed to load project'
  } finally {
    loading.value = false
  }
}

function navigateTo(routeName: string) {
  router.push({ name: routeName, params: { projectId: props.projectId } })
}

function startChat() {
  router.push({ name: 'project-chat', params: { projectId: props.projectId } })
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <div class="bg-white shadow">
      <div class="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <button @click="router.push({ name: 'landing' })" class="text-gray-400 hover:text-gray-600">
              <ArrowLeftIcon class="h-6 w-6" />
            </button>
            <div v-if="projectsStore.currentProject">
              <h1 class="text-2xl font-bold text-gray-900">{{ projectsStore.currentProject.name }}</h1>
              <p v-if="projectsStore.currentProject.description" class="text-sm text-gray-500">
                {{ projectsStore.currentProject.description }}
              </p>
            </div>
          </div>
          <button
            @click="showEditModal = true"
            class="inline-flex items-center px-3 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            <PencilIcon class="h-4 w-4 mr-2" />
            Edit
          </button>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      <!-- Loading -->
      <LoadingSpinner v-if="loading" text="Loading project..." />

      <!-- Error -->
      <ErrorAlert v-else-if="error" :message="error" />

      <!-- Content -->
      <template v-else-if="projectsStore.currentProject">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div class="bg-white p-6 rounded-lg shadow">
            <div class="flex items-center">
              <DocumentTextIcon class="h-10 w-10 text-blue-500" />
              <div class="ml-4">
                <p class="text-sm text-gray-500">Documents</p>
                <p class="text-2xl font-bold">{{ projectsStore.currentProject.stats.document_count }}</p>
              </div>
            </div>
          </div>
          <div class="bg-white p-6 rounded-lg shadow">
            <div class="flex items-center">
              <CpuChipIcon class="h-10 w-10 text-green-500" />
              <div class="ml-4">
                <p class="text-sm text-gray-500">Equipment</p>
                <p class="text-2xl font-bold">{{ projectsStore.currentProject.stats.equipment_count }}</p>
              </div>
            </div>
          </div>
          <div class="bg-white p-6 rounded-lg shadow">
            <div class="flex items-center">
              <DocumentDuplicateIcon class="h-10 w-10 text-purple-500" />
              <div class="ml-4">
                <p class="text-sm text-gray-500">Pages</p>
                <p class="text-2xl font-bold">{{ projectsStore.currentProject.stats.page_count }}</p>
              </div>
            </div>
          </div>
          <div class="bg-white p-6 rounded-lg shadow">
            <div class="flex items-center">
              <ChatBubbleLeftRightIcon class="h-10 w-10 text-orange-500" />
              <div class="ml-4">
                <p class="text-sm text-gray-500">Conversations</p>
                <p class="text-2xl font-bold">{{ projectsStore.currentProject.stats.conversation_count }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Quick Actions -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <button
            @click="startChat"
            class="flex items-center justify-center p-6 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <ChatBubbleLeftRightIcon class="h-6 w-6 mr-3" />
            <span class="text-lg font-medium">Start Chat</span>
          </button>
          <button
            @click="navigateTo('project-documents')"
            class="flex items-center justify-center p-6 bg-white border-2 border-gray-200 rounded-lg hover:border-blue-500 transition-colors"
          >
            <DocumentTextIcon class="h-6 w-6 mr-3 text-gray-600" />
            <span class="text-lg font-medium text-gray-700">Manage Documents</span>
          </button>
          <button
            @click="navigateTo('project-conversations')"
            class="flex items-center justify-center p-6 bg-white border-2 border-gray-200 rounded-lg hover:border-blue-500 transition-colors"
          >
            <ChatBubbleLeftRightIcon class="h-6 w-6 mr-3 text-gray-600" />
            <span class="text-lg font-medium text-gray-700">View Conversations</span>
          </button>
        </div>

        <!-- Project Info -->
        <div class="bg-white rounded-lg shadow p-6">
          <h2 class="text-lg font-semibold mb-4">Project Details</h2>
          <dl class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div v-if="projectsStore.currentProject.facility_name">
              <dt class="text-sm text-gray-500">Facility</dt>
              <dd class="text-sm font-medium">{{ projectsStore.currentProject.facility_name }}</dd>
            </div>
            <div v-if="projectsStore.currentProject.system_type">
              <dt class="text-sm text-gray-500">System Type</dt>
              <dd class="text-sm font-medium">{{ projectsStore.currentProject.system_type }}</dd>
            </div>
            <div>
              <dt class="text-sm text-gray-500">Status</dt>
              <dd class="text-sm font-medium capitalize">{{ projectsStore.currentProject.status }}</dd>
            </div>
            <div v-if="projectsStore.currentProject.tags?.length">
              <dt class="text-sm text-gray-500">Tags</dt>
              <dd class="flex flex-wrap gap-1 mt-1">
                <span
                  v-for="tag in projectsStore.currentProject.tags"
                  :key="tag"
                  class="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded"
                >
                  {{ tag }}
                </span>
              </dd>
            </div>
          </dl>
          <div v-if="projectsStore.currentProject.notes" class="mt-4">
            <dt class="text-sm text-gray-500">Notes</dt>
            <dd class="text-sm mt-1 whitespace-pre-wrap">{{ projectsStore.currentProject.notes }}</dd>
          </div>
        </div>
      </template>
    </div>

    <!-- Edit Modal -->
    <ProjectForm
      v-if="showEditModal && projectsStore.currentProject"
      :project="{ ...projectsStore.currentProject, id: projectsStore.currentProject.id }"
      @close="showEditModal = false"
      @updated="showEditModal = false; loadProject()"
    />
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend-vue/src/views/ProjectDashboardView.vue
git commit -m "feat(views): add Project Dashboard view with stats and quick actions"
```

---

## Phase 3 & 4: Remaining Tasks (Summary)

Due to the extensive nature of this plan, I'll summarize the remaining tasks. Each follows the same pattern as above.

### Phase 3: Conversations & Chat Backend

- **Task 3.1**: Create Conversations API Router (`backend/app/api/routes/conversations.py`)
- **Task 3.2**: Create Messages API with RAG integration
- **Task 3.3**: Modify RAG service for project-scoped search
- **Task 3.4**: Modify search API to accept project_id parameter
- **Task 3.5**: Add global search endpoint with project info in results

### Phase 4: Chat Interface Frontend

- **Task 4.1**: Create Conversations API module and Pinia store
- **Task 4.2**: Create Chat Pinia store for active source state
- **Task 4.3**: Create ChatPanel component (20% width)
- **Task 4.4**: Create ChatMessages component with message rendering
- **Task 4.5**: Create ChatInput component
- **Task 4.6**: Create SourceCard component with thumbnail preview
- **Task 4.7**: Create ProjectChatView with 20/80 split layout
- **Task 4.8**: Modify PdfViewer to support region highlighting
- **Task 4.9**: Create GlobalSearchView for landing page search results
- **Task 4.10**: Create ProjectDocumentsView (scoped document management)
- **Task 4.11**: Create ProjectConversationsView (conversation list)
- **Task 4.12**: Update App.vue to handle project context in layout
- **Task 4.13**: Final integration testing and polish

---

## Verification Checklist

After completing all tasks, verify:

1. [ ] Can create a new project with all metadata fields
2. [ ] Can upload documents to a specific project
3. [ ] Documents are correctly associated with projects
4. [ ] Can create and continue conversations within a project
5. [ ] Chat responses include source references
6. [ ] Clicking source cards navigates to PDF with highlighting
7. [ ] Global search returns results with project information
8. [ ] Project-scoped search only returns results from that project
9. [ ] Existing data migrated to default project without loss
10. [ ] All API endpoints respond correctly
11. [ ] Frontend builds without errors
12. [ ] Docker containers run correctly

---

## Commands Reference

```bash
# Run database migration
psql -d electrical_rag -f scripts/migrate_to_projects.sql

# Backend development
cd backend && uvicorn app.main:app --reload

# Frontend development
cd frontend-vue && npm run dev

# Build frontend
cd frontend-vue && npm run build

# Docker build and run
docker-compose up --build
```
