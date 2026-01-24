# Electrical Drawing RAG System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a RAG system that enables natural language search of electrical plant drawings, extracting equipment tags, relationships, and enabling semantic search with AI-generated answers.

**Architecture:** FastAPI backend with PostgreSQL+pgvector for hybrid search (exact/semantic/keyword), PaddleOCR for document processing, sentence-transformers for embeddings, Claude API for RAG responses. Streamlit frontend for user interaction. Deployed on Railway.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, pgvector, PaddleOCR, sentence-transformers, Anthropic Claude API, Streamlit, Docker, Railway

---

## Phase 1: Project Foundation & Database

### Task 1: Initialize Project Structure

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/requirements.txt`
- Create: `frontend/requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `docker-compose.yml`

**Step 1: Create directory structure**

```bash
mkdir -p backend/app/{api/routes,services,models,db,utils}
mkdir -p backend/tests
mkdir -p frontend/{pages,components,static}
mkdir -p scripts docs
```

**Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
ENV/

# Environment
.env
.env.local

# IDE
.idea/
.vscode/
*.swp

# Data
uploads/
chroma_data/
*.pdf

# Docker
postgres_data/

# Testing
.pytest_cache/
.coverage
htmlcov/
```

**Step 3: Create .env.example**

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/electrical_rag

# LLM
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Application
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your-secret-key-here

# Storage
UPLOAD_DIR=/app/uploads
CHROMA_DIR=/app/chroma_data

# OCR Settings
OCR_LANGUAGE=en
OCR_DPI=300
```

**Step 4: Create backend/requirements.txt**

```txt
# FastAPI
fastapi==0.109.2
uvicorn[standard]==0.27.1
python-multipart==0.0.9

# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
pgvector==0.2.5
alembic==1.13.1

# OCR
paddleocr==2.7.0.3
paddlepaddle==2.6.0
pdf2image==1.17.0
Pillow==10.2.0

# ML/Embeddings
sentence-transformers==2.3.1
numpy==1.26.4

# LLM
anthropic==0.18.1

# Utilities
python-dotenv==1.0.1
pydantic==2.6.1
pydantic-settings==2.1.0
```

**Step 5: Create frontend/requirements.txt**

```txt
streamlit==1.31.1
requests==2.31.0
pandas==2.2.0
plotly==5.18.0
```

**Step 6: Create docker-compose.yml**

```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: electrical_rag
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_pgvector.sql:/docker-entrypoint-initdb.d/init.sql

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/electrical_rag
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./backend:/app
      - uploads:/app/uploads
      - chroma_data:/app/chroma_data
    depends_on:
      - db
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "8501:8501"
    environment:
      - BACKEND_URL=http://backend:8000
    volumes:
      - ./frontend:/app
    depends_on:
      - backend
    command: streamlit run app.py --server.port 8501 --server.address 0.0.0.0

volumes:
  postgres_data:
  uploads:
  chroma_data:
```

**Step 7: Create scripts/init_pgvector.sql**

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Step 8: Commit**

```bash
git init
git add .
git commit -m "chore: initialize project structure with docker-compose"
```

---

### Task 2: Database Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/database.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/session.py`

**Step 1: Create backend/app/models/__init__.py**

```python
from app.models.database import Base, Document, Page, Equipment, EquipmentLocation, EquipmentRelationship, Wire, SearchLog
```

**Step 2: Create backend/app/models/database.py**

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Index
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Document(Base):
    """Represents an electrical drawing document (PDF)"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    title = Column(String(500))
    drawing_number = Column(String(100), index=True)
    revision = Column(String(50))
    system = Column(String(100), index=True)
    area = Column(String(100), index=True)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    page_count = Column(Integer)
    upload_date = Column(DateTime, default=datetime.utcnow)
    processed = Column(Integer, default=0)  # 0=pending, 1=processing, 2=done, -1=error

    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")
    equipment = relationship("Equipment", back_populates="document")


class Page(Base):
    """Represents a single page from a drawing"""
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    ocr_text = Column(Text)
    processed_text = Column(Text)
    image_path = Column(String(500))
    embedding = Column(Vector(384))

    document = relationship("Document", back_populates="pages")
    equipment_locations = relationship("EquipmentLocation", back_populates="page")

    __table_args__ = (
        Index('idx_page_document_number', 'document_id', 'page_number'),
    )


class Equipment(Base):
    """Represents a piece of equipment found in drawings"""
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String(100), unique=True, nullable=False, index=True)
    equipment_type = Column(String(100), index=True)
    description = Column(Text)
    manufacturer = Column(String(200))
    model_number = Column(String(200))
    document_id = Column(Integer, ForeignKey("documents.id"))
    primary_page = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="equipment")
    locations = relationship("EquipmentLocation", back_populates="equipment")
    controls = relationship(
        "EquipmentRelationship",
        foreign_keys="EquipmentRelationship.source_id",
        back_populates="source"
    )
    controlled_by = relationship(
        "EquipmentRelationship",
        foreign_keys="EquipmentRelationship.target_id",
        back_populates="target"
    )


class EquipmentLocation(Base):
    """Tracks where equipment appears across all pages"""
    __tablename__ = "equipment_locations"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    x_min = Column(Float)
    y_min = Column(Float)
    x_max = Column(Float)
    y_max = Column(Float)
    context_text = Column(Text)

    equipment = relationship("Equipment", back_populates="locations")
    page = relationship("Page", back_populates="equipment_locations")

    __table_args__ = (
        Index('idx_equipment_page', 'equipment_id', 'page_id'),
    )


class EquipmentRelationship(Base):
    """Relationships between equipment (controls, powers, connects)"""
    __tablename__ = "equipment_relationships"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(50), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"))
    page_number = Column(Integer)
    confidence = Column(Float, default=1.0)

    source = relationship("Equipment", foreign_keys=[source_id], back_populates="controls")
    target = relationship("Equipment", foreign_keys=[target_id], back_populates="controlled_by")

    __table_args__ = (
        Index('idx_relationship_source', 'source_id', 'relationship_type'),
        Index('idx_relationship_target', 'target_id', 'relationship_type'),
    )


class Wire(Base):
    """Represents wires/cables in the system"""
    __tablename__ = "wires"

    id = Column(Integer, primary_key=True, index=True)
    wire_number = Column(String(100), unique=True, nullable=False, index=True)
    wire_type = Column(String(100))
    gauge = Column(String(50))
    color = Column(String(50))
    description = Column(Text)
    from_equipment_id = Column(Integer, ForeignKey("equipment.id"))
    from_terminal = Column(String(50))
    to_equipment_id = Column(Integer, ForeignKey("equipment.id"))
    to_terminal = Column(String(50))


class SearchLog(Base):
    """Log searches for analytics and improvement"""
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    query_type = Column(String(50))
    results_count = Column(Integer)
    response_time_ms = Column(Integer)
    user_feedback = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Step 3: Create backend/app/db/__init__.py**

```python
from app.db.session import get_db, init_db, SessionLocal, engine
```

**Step 4: Create backend/app/db/session.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for getting database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
```

**Step 5: Commit**

```bash
git add backend/app/models/ backend/app/db/
git commit -m "feat: add SQLAlchemy database models for documents, equipment, and relationships"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/models/schemas.py`

**Step 1: Create backend/app/models/schemas.py**

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class EquipmentType(str, Enum):
    FAN = "FAN"
    MOTOR = "MOTOR"
    VFD = "VFD"
    PUMP = "PUMP"
    BREAKER = "BREAKER"
    RELAY = "RELAY"
    PLC = "PLC"
    SENSOR = "SENSOR"
    VALVE = "VALVE"
    OTHER = "OTHER"


class RelationshipType(str, Enum):
    CONTROLS = "CONTROLS"
    POWERS = "POWERS"
    CONNECTS_TO = "CONNECTS_TO"
    FEEDS = "FEEDS"
    MONITORS = "MONITORS"


class QueryType(str, Enum):
    EQUIPMENT_LOOKUP = "equipment_lookup"
    RELATIONSHIP = "relationship"
    UPSTREAM_DOWNSTREAM = "upstream_downstream"
    WIRE_TRACE = "wire_trace"
    GENERAL = "general"


# Document Schemas
class DocumentBase(BaseModel):
    title: Optional[str] = None
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    system: Optional[str] = None
    area: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: int
    filename: str
    original_filename: str
    file_size: Optional[int]
    page_count: Optional[int]
    upload_date: datetime
    processed: int

    class Config:
        from_attributes = True


class PageSummary(BaseModel):
    id: int
    page_number: int
    equipment_count: int = 0

    class Config:
        from_attributes = True


class DocumentDetail(DocumentResponse):
    equipment_count: int = 0
    pages: List[PageSummary] = []


# Equipment Schemas
class EquipmentBrief(BaseModel):
    id: int
    tag: str
    equipment_type: Optional[str]

    class Config:
        from_attributes = True


class EquipmentCreate(BaseModel):
    tag: str
    equipment_type: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None


class EquipmentResponse(BaseModel):
    id: int
    tag: str
    equipment_type: Optional[str]
    description: Optional[str]
    manufacturer: Optional[str]
    model_number: Optional[str]
    document_id: Optional[int]
    primary_page: Optional[int]

    class Config:
        from_attributes = True


class EquipmentLocationResponse(BaseModel):
    document_filename: str
    document_title: Optional[str]
    page_number: int
    context_text: Optional[str]

    class Config:
        from_attributes = True


class RelationshipResponse(BaseModel):
    id: int
    source_tag: str
    target_tag: str
    relationship_type: str
    confidence: float

    class Config:
        from_attributes = True


class EquipmentDetail(EquipmentResponse):
    locations: List[EquipmentLocationResponse] = []
    controls: List[RelationshipResponse] = []
    controlled_by: List[RelationshipResponse] = []


class RelationshipCreate(BaseModel):
    source_tag: str
    target_tag: str
    relationship_type: RelationshipType


# Search Schemas
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    include_context: bool = True


class SearchResult(BaseModel):
    equipment: Optional[EquipmentBrief] = None
    document: DocumentResponse
    page_number: int
    relevance_score: float
    snippet: Optional[str] = None
    match_type: str


class SearchResponse(BaseModel):
    query: str
    query_type: QueryType
    results: List[SearchResult]
    total_count: int
    response_time_ms: int


class RAGResponse(BaseModel):
    query: str
    answer: str
    sources: List[SearchResult]
    query_type: QueryType
    confidence: float


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    message: str
    pages_detected: int


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
```

**Step 2: Update backend/app/models/__init__.py**

```python
from app.models.database import Base, Document, Page, Equipment, EquipmentLocation, EquipmentRelationship, Wire, SearchLog
from app.models.schemas import (
    DocumentResponse, DocumentDetail, DocumentCreate,
    EquipmentResponse, EquipmentDetail, EquipmentBrief, EquipmentCreate,
    SearchRequest, SearchResponse, SearchResult, RAGResponse,
    UploadResponse, HealthResponse, QueryType, RelationshipType,
    RelationshipCreate, RelationshipResponse
)
```

**Step 3: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add Pydantic schemas for API request/response validation"
```

---

## Phase 2: Document Processing Pipeline

### Task 4: OCR Service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/ocr_service.py`

**Step 1: Create backend/app/services/__init__.py**

```python
# Services module
```

**Step 2: Create backend/app/services/ocr_service.py**

```python
import os
import logging
from pathlib import Path
from typing import List, Dict
from pdf2image import convert_from_path
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self):
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=False,
            show_log=False
        )
        self.dpi = int(os.environ.get("OCR_DPI", 300))

    def pdf_to_images(self, pdf_path: str, output_dir: str) -> List[str]:
        """Convert PDF pages to images"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        images = convert_from_path(pdf_path, dpi=self.dpi)
        image_paths = []

        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f"page_{i + 1}.png")
            image.save(image_path, "PNG")
            image_paths.append(image_path)
            logger.info(f"Saved page {i + 1} to {image_path}")

        return image_paths

    def extract_text_from_image(self, image_path: str) -> Dict:
        """Extract text and bounding boxes from an image"""
        result = self.ocr.ocr(image_path, cls=True)

        if not result or not result[0]:
            return {"text": "", "elements": []}

        elements = []
        full_text_parts = []

        for line in result[0]:
            bbox, (text, confidence) = line

            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]

            elements.append({
                "text": text,
                "confidence": confidence,
                "bbox": {
                    "x_min": min(x_coords),
                    "y_min": min(y_coords),
                    "x_max": max(x_coords),
                    "y_max": max(y_coords)
                }
            })
            full_text_parts.append(text)

        return {
            "text": "\n".join(full_text_parts),
            "elements": elements
        }

    def process_document(self, pdf_path: str, document_id: int) -> List[Dict]:
        """Process entire PDF document"""
        output_dir = os.path.join(
            os.environ.get("UPLOAD_DIR", "/app/uploads"),
            f"doc_{document_id}",
            "pages"
        )

        image_paths = self.pdf_to_images(pdf_path, output_dir)

        pages_data = []
        for i, image_path in enumerate(image_paths):
            logger.info(f"Processing page {i + 1}/{len(image_paths)}")

            ocr_result = self.extract_text_from_image(image_path)

            pages_data.append({
                "page_number": i + 1,
                "image_path": image_path,
                "ocr_text": ocr_result["text"],
                "elements": ocr_result["elements"]
            })

        return pages_data


ocr_service = OCRService()
```

**Step 3: Commit**

```bash
git add backend/app/services/
git commit -m "feat: add OCR service with PaddleOCR for PDF text extraction"
```

---

### Task 5: Equipment Extraction Service

**Files:**
- Create: `backend/app/services/extraction_service.py`
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/tag_patterns.py`

**Step 1: Create backend/app/utils/__init__.py**

```python
# Utils module
```

**Step 2: Create backend/app/utils/tag_patterns.py**

```python
"""Equipment tag patterns for extraction"""

EQUIPMENT_PATTERNS = [
    # Standard patterns: TYPE-NUMBER or TYPE_NUMBER
    (r'\b(FAN|AHU|FCU|VAV|MAU|EF|SF|RF)-?\d{1,4}[A-Z]?\b', 'FAN'),
    (r'\b(MOT|MTR|M)-?\d{1,4}[A-Z]?\b', 'MOTOR'),
    (r'\b(VFD|VSD|AFD)-?\d{1,4}[A-Z]?\b', 'VFD'),
    (r'\b(PMP|P)-?\d{1,4}[A-Z]?\b', 'PUMP'),
    (r'\b(BKR|CB|MCCB)-?\d{1,4}[A-Z]?\b', 'BREAKER'),
    (r'\b(RLY|CR|TR)-?\d{1,4}[A-Z]?\b', 'RELAY'),
    (r'\b(PLC|DCS|PAC)-?\d{1,4}[A-Z]?\b', 'PLC'),
    (r'\b(TS|PS|FS|LS|PT|FT|LT|TT)-?\d{1,4}[A-Z]?\b', 'SENSOR'),
    (r'\b(CV|MOV|SOV|BV|GV)-?\d{1,4}[A-Z]?\b', 'VALVE'),
    (r'\b(MCC|SWG|PNL|DP)-?\d{1,4}[A-Z]?\b', 'PANEL'),
    (r'\b(XFMR|TX|TR)-?\d{1,4}[A-Z]?\b', 'TRANSFORMER'),
    # Generic pattern for unrecognized equipment
    (r'\b([A-Z]{2,4})-(\d{2,4})([A-Z]?)\b', 'OTHER'),
]

WIRE_PATTERNS = [
    r'\bW-?\d{3,5}\b',
    r'\b\d{3,4}[A-Z]{0,2}\b',
    r'\bCABLE-?\d{2,4}\b',
]

CONTROL_KEYWORDS = ['controls', 'controlled by', 'starts', 'stops', 'enables', 'interlocked']
POWER_KEYWORDS = ['powers', 'powered by', 'feeds', 'fed from', 'supplies']
```

**Step 3: Create backend/app/services/extraction_service.py**

```python
import re
import logging
from typing import List, Dict
from dataclasses import dataclass

from app.utils.tag_patterns import (
    EQUIPMENT_PATTERNS, WIRE_PATTERNS,
    CONTROL_KEYWORDS, POWER_KEYWORDS
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEquipment:
    tag: str
    equipment_type: str
    context: str
    bbox: Dict = None
    confidence: float = 1.0


class ExtractionService:
    """Extract equipment tags, wire numbers, and relationships from OCR text"""

    def extract_equipment_tags(self, text: str, elements: List[Dict] = None) -> List[ExtractedEquipment]:
        """Extract all equipment tags from text"""
        found_equipment: Dict[str, ExtractedEquipment] = {}

        for pattern, equip_type in EQUIPMENT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                tag = match.group(0).upper()

                if tag in found_equipment:
                    continue

                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()

                bbox = None
                if elements:
                    bbox = self._find_bbox_for_tag(tag, elements)

                found_equipment[tag] = ExtractedEquipment(
                    tag=tag,
                    equipment_type=equip_type,
                    context=context,
                    bbox=bbox
                )

        return list(found_equipment.values())

    def extract_wire_numbers(self, text: str) -> List[str]:
        """Extract wire numbers from text"""
        wires = set()

        for pattern in WIRE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            wires.update([w.upper() for w in matches])

        return list(wires)

    def extract_relationships(self, text: str, equipment_tags: List[str]) -> List[Dict]:
        """Extract relationships between equipment based on text context"""
        relationships = []

        if not equipment_tags:
            return relationships

        for keyword in CONTROL_KEYWORDS:
            pattern = rf'({"|".join(equipment_tags)})\s+{keyword}\s+({"|".join(equipment_tags)})'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                relationships.append({
                    "source": match.group(1).upper(),
                    "target": match.group(2).upper(),
                    "type": "CONTROLS",
                    "confidence": 0.8
                })

        for keyword in POWER_KEYWORDS:
            pattern = rf'({"|".join(equipment_tags)})\s+{keyword}\s+({"|".join(equipment_tags)})'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                relationships.append({
                    "source": match.group(1).upper(),
                    "target": match.group(2).upper(),
                    "type": "POWERS",
                    "confidence": 0.8
                })

        return relationships

    def _find_bbox_for_tag(self, tag: str, elements: List[Dict]) -> Dict:
        """Find bounding box for a tag in OCR elements"""
        for element in elements:
            if tag.upper() in element["text"].upper():
                return element["bbox"]
        return None

    def infer_equipment_type_from_context(self, tag: str, context: str) -> str:
        """Try to infer equipment type from surrounding context"""
        context_lower = context.lower()

        type_keywords = {
            'FAN': ['fan', 'air handler', 'exhaust', 'supply air', 'cfm'],
            'MOTOR': ['motor', 'hp', 'horsepower', 'rpm', 'kw'],
            'VFD': ['vfd', 'variable frequency', 'drive', 'inverter'],
            'PUMP': ['pump', 'gpm', 'head', 'flow'],
            'BREAKER': ['breaker', 'circuit', 'amp', 'disconnect'],
            'SENSOR': ['sensor', 'transmitter', 'temperature', 'pressure', 'level'],
            'VALVE': ['valve', 'actuator', 'damper'],
        }

        for equip_type, keywords in type_keywords.items():
            if any(kw in context_lower for kw in keywords):
                return equip_type

        return 'OTHER'


extraction_service = ExtractionService()
```

**Step 4: Commit**

```bash
git add backend/app/services/ backend/app/utils/
git commit -m "feat: add equipment extraction service with regex patterns"
```

---

### Task 6: Embedding Service

**Files:**
- Create: `backend/app/services/embedding_service.py`

**Step 1: Create backend/app/services/embedding_service.py**

```python
import logging
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings for semantic search"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = 384
        logger.info(f"Loaded embedding model: {model_name}")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            return [0.0] * self.embedding_dim

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        valid_texts = [t if t and t.strip() else " " for t in texts]
        embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
        return embeddings.tolist()

    def prepare_page_text_for_embedding(self, ocr_text: str, equipment_tags: List[str]) -> str:
        """Prepare page text for embedding with equipment context"""
        equipment_str = " ".join(equipment_tags) if equipment_tags else ""
        combined = f"{equipment_str} {ocr_text}"
        if len(combined) > 5000:
            combined = combined[:5000]
        return combined


embedding_service = EmbeddingService()
```

**Step 2: Commit**

```bash
git add backend/app/services/embedding_service.py
git commit -m "feat: add embedding service with sentence-transformers"
```

---

### Task 7: Document Processor Orchestrator

**Files:**
- Create: `backend/app/services/document_processor.py`

**Step 1: Create backend/app/services/document_processor.py**

```python
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
```

**Step 2: Commit**

```bash
git add backend/app/services/document_processor.py
git commit -m "feat: add document processor orchestrating OCR, extraction, and embedding"
```

---

## Phase 3: Search & RAG Engine

### Task 8: Search Service

**Files:**
- Create: `backend/app/services/search_service.py`

**Step 1: Create backend/app/services/search_service.py**

```python
import re
import time
import logging
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func

from app.models.database import Document, Page, Equipment, EquipmentLocation, EquipmentRelationship
from app.models.schemas import QueryType, SearchResult, SearchResponse, DocumentResponse, EquipmentBrief
from app.services.embedding_service import embedding_service
from app.services.extraction_service import extraction_service

logger = logging.getLogger(__name__)


class SearchService:
    """Hybrid search: exact match + semantic + keyword"""

    def classify_query(self, query: str) -> QueryType:
        """Determine the type of query"""
        query_lower = query.lower()

        has_equipment_tag = bool(re.search(r'\b[A-Z]{2,4}-?\d{2,4}\b', query, re.IGNORECASE))

        if any(word in query_lower for word in ['where is', 'find', 'locate', 'which drawing', 'which page']):
            return QueryType.EQUIPMENT_LOOKUP

        if any(word in query_lower for word in ['control', 'controls', 'controlled by', 'what controls']):
            return QueryType.RELATIONSHIP

        if any(word in query_lower for word in ['upstream', 'downstream', 'feeds', 'powered by', 'powers']):
            return QueryType.UPSTREAM_DOWNSTREAM

        if any(word in query_lower for word in ['wire', 'cable', 'conductor', 'w-']):
            return QueryType.WIRE_TRACE

        if has_equipment_tag:
            return QueryType.EQUIPMENT_LOOKUP

        return QueryType.GENERAL

    def search(self, db: Session, query: str, limit: int = 10) -> SearchResponse:
        """Perform hybrid search"""
        start_time = time.time()

        query_type = self.classify_query(query)
        results: List[SearchResult] = []

        equipment_in_query = extraction_service.extract_equipment_tags(query)
        equipment_tags = [eq.tag for eq in equipment_in_query]

        # 1. Exact equipment match
        if equipment_tags:
            exact_results = self._exact_equipment_search(db, equipment_tags, limit)
            results.extend(exact_results)

        # 2. Semantic search
        if len(results) < limit:
            semantic_results = self._semantic_search(db, query, limit - len(results))
            results.extend(semantic_results)

        # 3. Keyword search as fallback
        if len(results) < limit:
            keyword_results = self._keyword_search(db, query, limit - len(results))
            existing_pages = {(r.document.id, r.page_number) for r in results}
            for kr in keyword_results:
                if (kr.document.id, kr.page_number) not in existing_pages:
                    results.append(kr)

        response_time = int((time.time() - start_time) * 1000)

        return SearchResponse(
            query=query,
            query_type=query_type,
            results=results[:limit],
            total_count=len(results),
            response_time_ms=response_time
        )

    def _exact_equipment_search(self, db: Session, tags: List[str], limit: int) -> List[SearchResult]:
        """Search for exact equipment tag matches"""
        results = []

        for tag in tags:
            equipment = db.query(Equipment).filter(
                func.upper(Equipment.tag) == tag.upper()
            ).first()

            if equipment:
                locations = db.query(EquipmentLocation).filter(
                    EquipmentLocation.equipment_id == equipment.id
                ).join(Page).join(Document).limit(limit).all()

                for loc in locations:
                    page = loc.page
                    doc = page.document

                    doc_response = DocumentResponse(
                        id=doc.id,
                        filename=doc.filename,
                        original_filename=doc.original_filename,
                        title=doc.title,
                        drawing_number=doc.drawing_number,
                        revision=doc.revision,
                        system=doc.system,
                        area=doc.area,
                        file_size=doc.file_size,
                        page_count=doc.page_count,
                        upload_date=doc.upload_date,
                        processed=doc.processed
                    )

                    results.append(SearchResult(
                        equipment=EquipmentBrief(id=equipment.id, tag=equipment.tag, equipment_type=equipment.equipment_type),
                        document=doc_response,
                        page_number=page.page_number,
                        relevance_score=1.0,
                        snippet=loc.context_text,
                        match_type="exact"
                    ))

        return results

    def _semantic_search(self, db: Session, query: str, limit: int) -> List[SearchResult]:
        """Search using vector similarity"""
        query_embedding = embedding_service.generate_embedding(query)

        sql = text("""
            SELECT
                p.id,
                p.document_id,
                p.page_number,
                p.ocr_text,
                d.filename,
                d.original_filename,
                d.title,
                d.drawing_number,
                d.revision,
                d.system,
                d.area,
                d.file_size,
                d.page_count,
                d.upload_date,
                d.processed,
                1 - (p.embedding <=> :embedding::vector) as similarity
            FROM pages p
            JOIN documents d ON p.document_id = d.id
            WHERE p.embedding IS NOT NULL
            ORDER BY p.embedding <=> :embedding::vector
            LIMIT :limit
        """)

        result = db.execute(sql, {"embedding": str(query_embedding), "limit": limit})

        results = []
        for row in result:
            doc_response = DocumentResponse(
                id=row.document_id,
                filename=row.filename,
                original_filename=row.original_filename,
                title=row.title,
                drawing_number=row.drawing_number,
                revision=row.revision,
                system=row.system,
                area=row.area,
                file_size=row.file_size,
                page_count=row.page_count,
                upload_date=row.upload_date,
                processed=row.processed
            )

            snippet = row.ocr_text[:200] + "..." if row.ocr_text and len(row.ocr_text) > 200 else row.ocr_text

            results.append(SearchResult(
                equipment=None,
                document=doc_response,
                page_number=row.page_number,
                relevance_score=float(row.similarity),
                snippet=snippet,
                match_type="semantic"
            ))

        return results

    def _keyword_search(self, db: Session, query: str, limit: int) -> List[SearchResult]:
        """Full-text keyword search"""
        search_term = f"%{query}%"

        pages = db.query(Page).join(Document).filter(
            or_(
                Page.ocr_text.ilike(search_term),
                Document.title.ilike(search_term),
                Document.drawing_number.ilike(search_term)
            )
        ).limit(limit).all()

        results = []
        for page in pages:
            doc = page.document
            doc_response = DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                title=doc.title,
                drawing_number=doc.drawing_number,
                revision=doc.revision,
                system=doc.system,
                area=doc.area,
                file_size=doc.file_size,
                page_count=doc.page_count,
                upload_date=doc.upload_date,
                processed=doc.processed
            )

            snippet = page.ocr_text[:200] + "..." if page.ocr_text and len(page.ocr_text) > 200 else page.ocr_text

            results.append(SearchResult(
                equipment=None,
                document=doc_response,
                page_number=page.page_number,
                relevance_score=0.5,
                snippet=snippet,
                match_type="keyword"
            ))

        return results

    def get_equipment_relationships(self, db: Session, equipment_tag: str, direction: str = "both") -> dict:
        """Get equipment relationships (controls/controlled_by)"""
        equipment = db.query(Equipment).filter(
            func.upper(Equipment.tag) == equipment_tag.upper()
        ).first()

        if not equipment:
            return {"error": f"Equipment {equipment_tag} not found"}

        result = {
            "equipment": equipment.tag,
            "controls": [],
            "controlled_by": [],
            "powers": [],
            "powered_by": []
        }

        if direction in ["both", "outgoing"]:
            outgoing = db.query(EquipmentRelationship).filter(
                EquipmentRelationship.source_id == equipment.id
            ).all()

            for rel in outgoing:
                target = db.query(Equipment).filter(Equipment.id == rel.target_id).first()
                if target:
                    if rel.relationship_type == "CONTROLS":
                        result["controls"].append(target.tag)
                    elif rel.relationship_type == "POWERS":
                        result["powers"].append(target.tag)

        if direction in ["both", "incoming"]:
            incoming = db.query(EquipmentRelationship).filter(
                EquipmentRelationship.target_id == equipment.id
            ).all()

            for rel in incoming:
                source = db.query(Equipment).filter(Equipment.id == rel.source_id).first()
                if source:
                    if rel.relationship_type == "CONTROLS":
                        result["controlled_by"].append(source.tag)
                    elif rel.relationship_type == "POWERS":
                        result["powered_by"].append(source.tag)

        return result

    def get_upstream_equipment(self, db: Session, equipment_tag: str, depth: int = 3) -> List[str]:
        """Get upstream equipment chain"""
        visited = set()
        upstream = []

        def traverse(tag: str, current_depth: int):
            if current_depth > depth or tag in visited:
                return
            visited.add(tag)

            equipment = db.query(Equipment).filter(
                func.upper(Equipment.tag) == tag.upper()
            ).first()

            if not equipment:
                return

            incoming = db.query(EquipmentRelationship).filter(
                EquipmentRelationship.target_id == equipment.id,
                EquipmentRelationship.relationship_type.in_(["POWERS", "FEEDS"])
            ).all()

            for rel in incoming:
                source = db.query(Equipment).filter(Equipment.id == rel.source_id).first()
                if source and source.tag not in visited:
                    upstream.append(source.tag)
                    traverse(source.tag, current_depth + 1)

        traverse(equipment_tag, 0)
        return upstream


search_service = SearchService()
```

**Step 2: Commit**

```bash
git add backend/app/services/search_service.py
git commit -m "feat: add hybrid search service with exact, semantic, and keyword search"
```

---

### Task 9: RAG Service

**Files:**
- Create: `backend/app/services/rag_service.py`

**Step 1: Create backend/app/services/rag_service.py**

```python
import os
import logging
from typing import List
from sqlalchemy.orm import Session
import anthropic

from app.models.schemas import RAGResponse, SearchResult, QueryType
from app.services.search_service import search_service

logger = logging.getLogger(__name__)


class RAGService:
    """Generate natural language answers using Claude"""

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            self.client = None
            logger.warning("ANTHROPIC_API_KEY not set, RAG responses will be limited")

    def generate_answer(self, db: Session, query: str) -> RAGResponse:
        """Generate an answer using search results and LLM"""

        search_response = search_service.search(db, query, limit=5)

        additional_context = self._get_additional_context(db, query, search_response.query_type)

        context = self._build_context(search_response.results, additional_context)

        if self.client:
            answer = self._call_llm(query, context, search_response.query_type)
        else:
            answer = self._generate_fallback_answer(query, search_response.results, additional_context)

        return RAGResponse(
            query=query,
            answer=answer,
            sources=search_response.results,
            query_type=search_response.query_type,
            confidence=0.9 if self.client else 0.6
        )

    def _get_additional_context(self, db: Session, query: str, query_type: QueryType) -> dict:
        """Get additional context based on query type"""
        context = {}

        from app.services.extraction_service import extraction_service
        equipment = extraction_service.extract_equipment_tags(query)

        if equipment and query_type in [QueryType.RELATIONSHIP, QueryType.UPSTREAM_DOWNSTREAM]:
            tag = equipment[0].tag

            relationships = search_service.get_equipment_relationships(db, tag)
            context["relationships"] = relationships

            if query_type == QueryType.UPSTREAM_DOWNSTREAM:
                upstream = search_service.get_upstream_equipment(db, tag)
                context["upstream"] = upstream

        return context

    def _build_context(self, results: List[SearchResult], additional_context: dict) -> str:
        """Build context string for LLM"""
        parts = []

        parts.append("=== RELEVANT DOCUMENT EXCERPTS ===")
        for i, result in enumerate(results, 1):
            parts.append(f"\n[Source {i}] Document: {result.document.filename}, Page {result.page_number}")
            if result.equipment:
                parts.append(f"Equipment: {result.equipment.tag}")
            if result.snippet:
                parts.append(f"Content: {result.snippet}")

        if "relationships" in additional_context:
            rel = additional_context["relationships"]
            parts.append(f"\n=== EQUIPMENT RELATIONSHIPS FOR {rel.get('equipment', 'N/A')} ===")
            if rel.get("controls"):
                parts.append(f"Controls: {', '.join(rel['controls'])}")
            if rel.get("controlled_by"):
                parts.append(f"Controlled by: {', '.join(rel['controlled_by'])}")
            if rel.get("powers"):
                parts.append(f"Powers: {', '.join(rel['powers'])}")
            if rel.get("powered_by"):
                parts.append(f"Powered by: {', '.join(rel['powered_by'])}")

        if "upstream" in additional_context and additional_context["upstream"]:
            parts.append(f"\n=== UPSTREAM EQUIPMENT CHAIN ===")
            parts.append(" -> ".join(additional_context["upstream"]))

        return "\n".join(parts)

    def _call_llm(self, query: str, context: str, query_type: QueryType) -> str:
        """Call Claude API to generate answer"""

        system_prompt = """You are an electrical engineering assistant helping users find information in plant electrical drawings.

Your responsibilities:
1. Answer questions about equipment location, control relationships, and wiring
2. Always cite specific document names and page numbers when referencing information
3. Be precise and technical in your responses
4. If information is not found in the provided context, say so clearly
5. For relationship questions, explain the control hierarchy clearly

Format your response clearly with:
- Direct answer to the question
- Document references (Document: X, Page: Y)
- Any relevant additional context"""

        user_prompt = f"""Based on the following context from our electrical drawing database, please answer this question:

Question: {query}

{context}

Provide a clear, technical answer with document references."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return self._generate_fallback_answer(query, [], {})

    def _generate_fallback_answer(self, query: str, results: List[SearchResult], additional_context: dict) -> str:
        """Generate a basic answer without LLM"""
        if not results:
            return f"No relevant information found for: {query}"

        parts = [f"Found {len(results)} relevant result(s) for your query:\n"]

        for i, result in enumerate(results, 1):
            parts.append(f"{i}. Document: {result.document.filename}, Page {result.page_number}")
            if result.equipment:
                parts.append(f"   Equipment: {result.equipment.tag}")
            if result.snippet:
                parts.append(f"   Preview: {result.snippet[:100]}...")
            parts.append("")

        if "relationships" in additional_context:
            rel = additional_context["relationships"]
            parts.append(f"\nRelationships for {rel.get('equipment', 'N/A')}:")
            if rel.get("controls"):
                parts.append(f"  Controls: {', '.join(rel['controls'])}")
            if rel.get("controlled_by"):
                parts.append(f"  Controlled by: {', '.join(rel['controlled_by'])}")

        return "\n".join(parts)


rag_service = RAGService()
```

**Step 2: Commit**

```bash
git add backend/app/services/rag_service.py
git commit -m "feat: add RAG service with Claude API integration"
```

---

## Phase 4: API Backend

### Task 10: FastAPI Main Application

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`

**Step 1: Create backend/app/__init__.py**

```python
# Electrical Drawing RAG Backend
```

**Step 2: Create backend/app/config.py**

```python
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = os.environ.get("ENVIRONMENT", "development")
    debug: bool = environment == "development"

    database_url: str = os.environ.get("DATABASE_URL", "")

    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")

    upload_dir: str = os.environ.get("UPLOAD_DIR", "/app/uploads")
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    cors_origins: list = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 3: Create backend/app/main.py**

```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, search, equipment, health
from app.db.session import init_db
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting up...")
    init_db()
    logger.info("Database initialized")

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="Electrical Drawing RAG API",
    description="API for searching and querying electrical plant drawings",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(equipment.router, prefix="/api/equipment", tags=["Equipment"])


@app.get("/")
async def root():
    return {
        "message": "Electrical Drawing RAG API",
        "docs": "/docs",
        "health": "/health"
    }
```

**Step 4: Commit**

```bash
git add backend/app/__init__.py backend/app/main.py backend/app/config.py
git commit -m "feat: add FastAPI main application with CORS and lifecycle"
```

---

### Task 11: API Routes - Health & Documents

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/api/routes/documents.py`

**Step 1: Create backend/app/api/__init__.py**

```python
# API module
```

**Step 2: Create backend/app/api/routes/__init__.py**

```python
from app.api.routes import health, documents, search, equipment
```

**Step 3: Create backend/app/api/routes/health.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Check API and database health"""
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        version="1.0.0"
    )
```

**Step 4: Create backend/app/api/routes/documents.py**

```python
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
```

**Step 5: Commit**

```bash
git add backend/app/api/
git commit -m "feat: add health and documents API routes"
```

---

### Task 12: API Routes - Search & Equipment

**Files:**
- Create: `backend/app/api/routes/search.py`
- Create: `backend/app/api/routes/equipment.py`

**Step 1: Create backend/app/api/routes/search.py**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import SearchRequest, SearchResponse, RAGResponse
from app.services.search_service import search_service
from app.services.rag_service import rag_service

router = APIRouter()


@router.get("/", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Search for equipment, documents, or general queries"""
    return search_service.search(db, q, limit)


@router.post("/ask", response_model=RAGResponse)
async def ask_question(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Ask a natural language question and get an AI-generated answer"""
    return rag_service.generate_answer(db, request.query)


@router.get("/equipment/{tag}/relationships")
async def get_equipment_relationships(
    tag: str,
    direction: str = Query("both", pattern="^(both|incoming|outgoing)$"),
    db: Session = Depends(get_db)
):
    """Get control/power relationships for equipment"""
    return search_service.get_equipment_relationships(db, tag, direction)


@router.get("/equipment/{tag}/upstream")
async def get_upstream_equipment(
    tag: str,
    depth: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """Get upstream equipment chain"""
    upstream = search_service.get_upstream_equipment(db, tag, depth)
    return {"equipment": tag, "upstream_chain": upstream}
```

**Step 2: Create backend/app/api/routes/equipment.py**

```python
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.database import Equipment, EquipmentRelationship
from app.models.schemas import EquipmentResponse, EquipmentDetail, RelationshipCreate

router = APIRouter()


@router.get("/", response_model=List[EquipmentResponse])
async def list_equipment(
    skip: int = 0,
    limit: int = 100,
    equipment_type: str = None,
    search: str = None,
    db: Session = Depends(get_db)
):
    """List all equipment with optional filtering"""
    query = db.query(Equipment)

    if equipment_type:
        query = query.filter(Equipment.equipment_type == equipment_type)

    if search:
        query = query.filter(Equipment.tag.ilike(f"%{search}%"))

    equipment = query.offset(skip).limit(limit).all()
    return equipment


@router.get("/types")
async def get_equipment_types(db: Session = Depends(get_db)):
    """Get list of all equipment types"""
    types = db.query(Equipment.equipment_type).distinct().all()
    return [t[0] for t in types if t[0]]


@router.get("/{tag}", response_model=EquipmentDetail)
async def get_equipment(tag: str, db: Session = Depends(get_db)):
    """Get detailed equipment information"""
    equipment = db.query(Equipment).filter(
        func.upper(Equipment.tag) == tag.upper()
    ).first()

    if not equipment:
        raise HTTPException(status_code=404, detail=f"Equipment {tag} not found")

    locations = []
    for loc in equipment.locations:
        page = loc.page
        doc = page.document
        locations.append({
            "document_filename": doc.filename,
            "document_title": doc.title,
            "page_number": page.page_number,
            "context_text": loc.context_text
        })

    controls = []
    for rel in equipment.controls:
        target = db.query(Equipment).filter(Equipment.id == rel.target_id).first()
        if target:
            controls.append({
                "id": rel.id,
                "source_tag": equipment.tag,
                "target_tag": target.tag,
                "relationship_type": rel.relationship_type,
                "confidence": rel.confidence
            })

    controlled_by = []
    for rel in equipment.controlled_by:
        source = db.query(Equipment).filter(Equipment.id == rel.source_id).first()
        if source:
            controlled_by.append({
                "id": rel.id,
                "source_tag": source.tag,
                "target_tag": equipment.tag,
                "relationship_type": rel.relationship_type,
                "confidence": rel.confidence
            })

    return EquipmentDetail(
        id=equipment.id,
        tag=equipment.tag,
        equipment_type=equipment.equipment_type,
        description=equipment.description,
        manufacturer=equipment.manufacturer,
        model_number=equipment.model_number,
        document_id=equipment.document_id,
        primary_page=equipment.primary_page,
        locations=locations,
        controls=controls,
        controlled_by=controlled_by
    )


@router.post("/relationships")
async def add_relationship(
    relationship: RelationshipCreate,
    db: Session = Depends(get_db)
):
    """Manually add a relationship between equipment"""
    source = db.query(Equipment).filter(
        func.upper(Equipment.tag) == relationship.source_tag.upper()
    ).first()
    target = db.query(Equipment).filter(
        func.upper(Equipment.tag) == relationship.target_tag.upper()
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail=f"Source equipment {relationship.source_tag} not found")
    if not target:
        raise HTTPException(status_code=404, detail=f"Target equipment {relationship.target_tag} not found")

    existing = db.query(EquipmentRelationship).filter(
        EquipmentRelationship.source_id == source.id,
        EquipmentRelationship.target_id == target.id,
        EquipmentRelationship.relationship_type == relationship.relationship_type
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")

    new_rel = EquipmentRelationship(
        source_id=source.id,
        target_id=target.id,
        relationship_type=relationship.relationship_type,
        confidence=1.0
    )
    db.add(new_rel)
    db.commit()

    return {"message": "Relationship created successfully"}
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/search.py backend/app/api/routes/equipment.py
git commit -m "feat: add search and equipment API routes"
```

---

### Task 13: Backend Dockerfile

**Files:**
- Create: `backend/Dockerfile`

**Step 1: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/chroma_data

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Step 2: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat: add backend Dockerfile with OCR dependencies"
```

---

## Phase 5: Frontend UI

### Task 14: Streamlit Main App

**Files:**
- Create: `frontend/app.py`

**Step 1: Create frontend/app.py**

```python
import streamlit as st
import requests
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Electrical Drawing Search",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 1rem;
    }
    .search-box {
        padding: 1rem;
        background-color: #F3F4F6;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .result-card {
        padding: 1rem;
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .equipment-tag {
        background-color: #DBEAFE;
        color: #1E40AF;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("Electrical RAG")
    st.markdown("---")

    try:
        stats_response = requests.get(f"{BACKEND_URL}/api/documents/", timeout=5)
        if stats_response.status_code == 200:
            docs = stats_response.json()
            st.metric("Total Documents", len(docs))

        equip_response = requests.get(f"{BACKEND_URL}/api/equipment/", timeout=5)
        if equip_response.status_code == 200:
            equipment = equip_response.json()
            st.metric("Total Equipment", len(equipment))
    except Exception:
        st.warning("Backend not connected")

    st.markdown("---")
    st.markdown("### Navigation")
    st.page_link("app.py", label="Search")
    st.page_link("pages/1_Upload.py", label="Upload")
    st.page_link("pages/2_Equipment.py", label="Equipment")
    st.page_link("pages/3_Documents.py", label="Documents")

st.markdown('<p class="main-header">Electrical Drawing Search</p>', unsafe_allow_html=True)

st.markdown('<div class="search-box">', unsafe_allow_html=True)
query = st.text_input(
    "Ask a question or search for equipment",
    placeholder="e.g., Where is FAN-101? What controls the supply fan?",
    label_visibility="collapsed"
)

col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    search_mode = st.selectbox("Mode", ["AI Answer", "Search Only"], label_visibility="collapsed")
with col2:
    search_button = st.button("Search", type="primary", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

if search_button and query:
    with st.spinner("Searching..."):
        try:
            if search_mode == "AI Answer":
                response = requests.post(
                    f"{BACKEND_URL}/api/search/ask",
                    json={"query": query},
                    timeout=30
                )
            else:
                response = requests.get(
                    f"{BACKEND_URL}/api/search/",
                    params={"q": query},
                    timeout=10
                )

            if response.status_code == 200:
                data = response.json()

                if "answer" in data:
                    st.markdown("### Answer")
                    st.markdown(data["answer"])
                    st.markdown("---")

                st.markdown("### Sources")

                results = data.get("sources", data.get("results", []))

                if not results:
                    st.info("No results found. Try a different search term.")
                else:
                    for i, result in enumerate(results):
                        with st.container():
                            col1, col2 = st.columns([4, 1])

                            with col1:
                                doc = result.get("document", {})
                                st.markdown(f"**{doc.get('original_filename', doc.get('filename', 'Unknown'))}** - Page {result.get('page_number', 'N/A')}")

                                if result.get("equipment"):
                                    st.markdown(f'<span class="equipment-tag">{result["equipment"].get("tag", "")}</span>', unsafe_allow_html=True)

                                if result.get("snippet"):
                                    snippet = result.get("snippet", "")
                                    st.caption(snippet[:200] + "..." if len(snippet) > 200 else snippet)

                            with col2:
                                if st.button(f"View Page", key=f"view_{i}"):
                                    st.session_state.view_doc = doc.get("id")
                                    st.session_state.view_page = result.get("page_number")

                            st.markdown("---")
            else:
                st.error(f"Search failed: {response.text}")

        except requests.exceptions.ConnectionError:
            st.error("Could not connect to backend. Please ensure the API is running.")
        except Exception as e:
            st.error(f"Error: {str(e)}")

if not query:
    st.markdown("### Example Queries")

    examples = [
        "Where is FAN-101?",
        "What controls the main supply fan?",
        "What is upstream of VFD-205?",
        "Show me all equipment in HVAC"
    ]

    cols = st.columns(len(examples))
    for i, example in enumerate(examples):
        with cols[i]:
            if st.button(example, key=f"example_{i}"):
                st.session_state.example_query = example
                st.rerun()
```

**Step 2: Commit**

```bash
git add frontend/app.py
git commit -m "feat: add Streamlit main search page"
```

---

### Task 15: Upload Page

**Files:**
- Create: `frontend/pages/1_Upload.py`

**Step 1: Create frontend/pages/1_Upload.py**

```python
import streamlit as st
import requests
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Upload Drawings", page_icon="", layout="wide")

st.title("Upload Electrical Drawings")

st.markdown("""
Upload your electrical drawings (PDF format) to index them for searching.
The system will automatically:
- Extract text using OCR
- Identify equipment tags
- Detect control relationships
- Generate searchable embeddings
""")

uploaded_files = st.file_uploader(
    "Choose PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload one or more PDF files containing electrical drawings"
)

with st.expander("Optional: Add Document Metadata"):
    col1, col2 = st.columns(2)
    with col1:
        drawing_number = st.text_input("Drawing Number", placeholder="E-1234")
        revision = st.text_input("Revision", placeholder="A")
    with col2:
        system = st.selectbox("System", ["", "HVAC", "Electrical", "Plumbing", "Fire Protection", "Controls", "Other"])
        area = st.text_input("Area/Location", placeholder="Building A, Floor 2")

if st.button("Upload and Process", type="primary", disabled=not uploaded_files):
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Uploading {uploaded_file.name}...")

        try:
            files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}

            response = requests.post(
                f"{BACKEND_URL}/api/documents/upload",
                files=files,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                st.success(f"{uploaded_file.name} uploaded successfully! Document ID: {result['document_id']}")
            else:
                st.error(f"Failed to upload {uploaded_file.name}: {response.text}")

        except Exception as e:
            st.error(f"Error uploading {uploaded_file.name}: {str(e)}")

        progress_bar.progress((i + 1) / len(uploaded_files))

    status_text.text("Upload complete!")

st.markdown("---")
st.markdown("### Recent Documents")

try:
    response = requests.get(f"{BACKEND_URL}/api/documents/", params={"limit": 10}, timeout=10)
    if response.status_code == 200:
        documents = response.json()

        if not documents:
            st.info("No documents uploaded yet.")
        else:
            for doc in documents:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    st.text(doc.get("original_filename", doc.get("filename")))
                with col2:
                    status = doc.get("processed", 0)
                    if status == 0:
                        st.warning("Pending")
                    elif status == 1:
                        st.info("Processing...")
                    elif status == 2:
                        st.success("Ready")
                    else:
                        st.error("Error")
                with col3:
                    st.text(f"{doc.get('page_count', '?')} pages")
                with col4:
                    if st.button("Delete", key=f"delete_{doc['id']}"):
                        del_response = requests.delete(f"{BACKEND_URL}/api/documents/{doc['id']}", timeout=10)
                        if del_response.status_code == 200:
                            st.rerun()

except requests.exceptions.ConnectionError:
    st.error("Could not connect to backend.")
```

**Step 2: Commit**

```bash
git add frontend/pages/1_Upload.py
git commit -m "feat: add upload page for PDF documents"
```

---

### Task 16: Equipment & Documents Pages

**Files:**
- Create: `frontend/pages/2_Equipment.py`
- Create: `frontend/pages/3_Documents.py`

**Step 1: Create frontend/pages/2_Equipment.py**

```python
import streamlit as st
import requests
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Equipment Browser", page_icon="", layout="wide")

st.title("Equipment Browser")

col1, col2 = st.columns([2, 2])

with col1:
    search_term = st.text_input("Search equipment", placeholder="Enter equipment tag...")

with col2:
    try:
        types_response = requests.get(f"{BACKEND_URL}/api/equipment/types", timeout=5)
        if types_response.status_code == 200:
            equipment_types = ["All"] + types_response.json()
        else:
            equipment_types = ["All"]
    except Exception:
        equipment_types = ["All"]

    selected_type = st.selectbox("Filter by type", equipment_types)

try:
    params = {"limit": 100}
    if search_term:
        params["search"] = search_term
    if selected_type != "All":
        params["equipment_type"] = selected_type

    response = requests.get(f"{BACKEND_URL}/api/equipment/", params=params, timeout=10)

    if response.status_code == 200:
        equipment_list = response.json()

        if not equipment_list:
            st.info("No equipment found.")
        else:
            st.markdown(f"**Found {len(equipment_list)} equipment items**")

            for eq in equipment_list:
                with st.expander(f"{eq['tag']} - {eq.get('equipment_type', 'Unknown')}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f"**Tag:** {eq['tag']}")
                        st.markdown(f"**Type:** {eq.get('equipment_type', 'N/A')}")
                        if eq.get('description'):
                            st.markdown(f"**Description:** {eq['description'][:200]}...")

                    with col2:
                        if eq.get('manufacturer'):
                            st.markdown(f"**Manufacturer:** {eq['manufacturer']}")
                        if eq.get('model_number'):
                            st.markdown(f"**Model:** {eq['model_number']}")

                    if st.button("View Details", key=f"details_{eq['id']}"):
                        detail_response = requests.get(f"{BACKEND_URL}/api/equipment/{eq['tag']}", timeout=10)
                        if detail_response.status_code == 200:
                            detail = detail_response.json()

                            if detail.get('locations'):
                                st.markdown("**Locations:**")
                                for loc in detail['locations']:
                                    st.write(f"- {loc['document_filename']}, Page {loc['page_number']}")

                            if detail.get('controls'):
                                st.markdown("**Controls:**")
                                for rel in detail['controls']:
                                    st.write(f"- {rel['target_tag']}")

                            if detail.get('controlled_by'):
                                st.markdown("**Controlled by:**")
                                for rel in detail['controlled_by']:
                                    st.write(f"- {rel['source_tag']}")

except requests.exceptions.ConnectionError:
    st.error("Could not connect to backend.")
except Exception as e:
    st.error(f"Error: {str(e)}")
```

**Step 2: Create frontend/pages/3_Documents.py**

```python
import streamlit as st
import requests
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Documents", page_icon="", layout="wide")

st.title("Documents")

try:
    response = requests.get(f"{BACKEND_URL}/api/documents/", timeout=10)

    if response.status_code == 200:
        documents = response.json()

        if not documents:
            st.info("No documents uploaded yet. Go to Upload page to add documents.")
        else:
            for doc in documents:
                with st.expander(f"{doc.get('original_filename', doc['filename'])}"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.markdown(f"**Filename:** {doc['filename']}")
                        st.markdown(f"**Pages:** {doc.get('page_count', 'N/A')}")

                    with col2:
                        status = doc.get('processed', 0)
                        status_map = {0: "Pending", 1: "Processing", 2: "Ready", -1: "Error"}
                        st.markdown(f"**Status:** {status_map.get(status, 'Unknown')}")
                        if doc.get('upload_date'):
                            st.markdown(f"**Uploaded:** {doc['upload_date'][:10]}")

                    with col3:
                        if doc.get('system'):
                            st.markdown(f"**System:** {doc['system']}")
                        if doc.get('area'):
                            st.markdown(f"**Area:** {doc['area']}")

                    if st.button("View Details", key=f"doc_details_{doc['id']}"):
                        detail_response = requests.get(f"{BACKEND_URL}/api/documents/{doc['id']}", timeout=10)
                        if detail_response.status_code == 200:
                            detail = detail_response.json()
                            st.markdown(f"**Equipment found:** {detail.get('equipment_count', 0)}")

                            if detail.get('pages'):
                                st.markdown("**Pages:**")
                                for page in detail['pages']:
                                    st.write(f"- Page {page['page_number']}: {page.get('equipment_count', 0)} equipment")

except requests.exceptions.ConnectionError:
    st.error("Could not connect to backend.")
except Exception as e:
    st.error(f"Error: {str(e)}")
```

**Step 3: Commit**

```bash
git add frontend/pages/
git commit -m "feat: add equipment browser and documents pages"
```

---

### Task 17: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

**Step 1: Create frontend/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0
```

**Step 2: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat: add frontend Dockerfile"
```

---

## Phase 6: Railway Deployment

### Task 18: Railway Configuration

**Files:**
- Create: `railway.json`

**Step 1: Create railway.json**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

**Step 2: Commit**

```bash
git add railway.json
git commit -m "feat: add Railway deployment configuration"
```

---

### Task 19: Deploy to Railway

**Step 1: Install Railway CLI (if not installed)**

```bash
npm install -g @railway/cli
```

**Step 2: Login to Railway**

```bash
railway login
```

**Step 3: Initialize Railway project**

```bash
cd /Users/qilu/Code/Electric_RAG
railway init
# Select "Empty Project" when prompted
# Name: electrical-drawing-rag
```

**Step 4: Add PostgreSQL database**

```bash
railway add
# Select "PostgreSQL"
```

**Step 5: Enable pgvector extension**

In Railway dashboard:
1. Go to PostgreSQL service
2. Click "Data" tab
3. Run: `CREATE EXTENSION IF NOT EXISTS vector;`

**Step 6: Set environment variables**

```bash
railway variables set ANTHROPIC_API_KEY=<your-api-key>
railway variables set ENVIRONMENT=production
railway variables set UPLOAD_DIR=/app/uploads
```

**Step 7: Deploy backend**

```bash
cd backend
railway up
# Note the generated URL
```

**Step 8: Deploy frontend**

```bash
cd ../frontend
railway link
railway variables set BACKEND_URL=<backend-url-from-step-7>
railway up
```

**Step 9: Add persistent volume (in Railway dashboard)**

For backend service:
1. Settings -> Volumes -> Add Volume
2. Mount Path: `/app/uploads`
3. Size: 10GB

**Step 10: Generate public domains**

In Railway dashboard:
1. Backend service -> Settings -> Networking -> Generate Domain
2. Frontend service -> Settings -> Networking -> Generate Domain

---

## Phase 7: Testing

### Task 20: Basic API Tests

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_api.py`

**Step 1: Create backend/tests/__init__.py**

```python
# Tests module
```

**Step 2: Create backend/tests/test_api.py**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "degraded"]


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_search_empty_query():
    response = client.get("/api/search/", params={"q": ""})
    assert response.status_code == 422


def test_search_valid_query():
    response = client.get("/api/search/", params={"q": "FAN-101"})
    assert response.status_code == 200
    assert "results" in response.json()


def test_equipment_list():
    response = client.get("/api/equipment/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_documents_list():
    response = client.get("/api/documents/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Step 3: Run tests**

```bash
cd backend
pip install pytest
pytest tests/ -v
```

**Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: add basic API tests"
```

---

## Summary

This implementation plan covers:

1. **Phase 1**: Project foundation with Docker, database models, and schemas
2. **Phase 2**: Document processing pipeline (OCR, extraction, embeddings)
3. **Phase 3**: Search and RAG engine with hybrid search
4. **Phase 4**: FastAPI backend with all routes
5. **Phase 5**: Streamlit frontend with search, upload, and browsing
6. **Phase 6**: Railway deployment configuration
7. **Phase 7**: Basic API tests

**Total estimated tasks:** 20 bite-sized tasks
**Key technologies:** FastAPI, PostgreSQL+pgvector, PaddleOCR, sentence-transformers, Claude API, Streamlit, Railway
