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
    pages_processed: Optional[int] = 0
    upload_date: datetime
    processed: int
    processing_error: Optional[str] = None

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
