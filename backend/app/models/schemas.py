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


class ContentCategory(str, Enum):
    IO_LIST = "IO_LIST"
    EQUIPMENT_SCHEDULE = "EQUIPMENT_SCHEDULE"
    SEQUENCE_OF_OPERATION = "SEQUENCE_OF_OPERATION"
    COMMISSIONING = "COMMISSIONING"
    SUBMITTAL = "SUBMITTAL"
    OTHER = "OTHER"


class DataType(str, Enum):
    IO_POINT = "IO_POINT"
    SPECIFICATION = "SPECIFICATION"
    ALARM = "ALARM"
    SCHEDULE_ENTRY = "SCHEDULE_ENTRY"
    SEQUENCE = "SEQUENCE"


# Supplementary Document Schemas
class SupplementaryDocumentCreate(BaseModel):
    content_category: Optional[ContentCategory] = None


class SupplementaryDocumentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    original_filename: str
    document_type: str  # EXCEL, WORD
    content_category: Optional[str] = None
    file_size: Optional[int] = None
    processed: int
    processing_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SupplementaryChunkResponse(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    source_location: Optional[str] = None
    equipment_tags: Optional[str] = None  # JSON string

    class Config:
        from_attributes = True


class EquipmentDataResponse(BaseModel):
    id: int
    document_id: int
    equipment_tag: str
    equipment_id: Optional[int] = None
    match_confidence: Optional[float] = None
    data_type: str
    data_json: str
    source_location: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EquipmentAliasCreate(BaseModel):
    alias: str
    source: Optional[str] = None
    confidence: Optional[float] = None


class EquipmentAliasResponse(BaseModel):
    id: int
    equipment_id: int
    alias: str
    source: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EquipmentProfileResponse(BaseModel):
    id: int
    equipment_id: int
    profile_json: str
    last_updated: datetime

    class Config:
        from_attributes = True


# Project Schemas
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_type: Optional[str] = None
    facility_name: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)


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
    messages: List[MessageResponse] = Field(default_factory=list)


# Document Schemas
class DocumentBase(BaseModel):
    title: Optional[str] = None
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    system: Optional[str] = None
    area: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentProjectAssign(BaseModel):
    project_id: Optional[int] = None  # None means unassign from project


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
    drawing_type: Optional[str] = None

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
    document_id: int
    document_filename: str
    document_title: Optional[str]
    page_number: int
    context_text: Optional[str]

    class Config:
        from_attributes = True


# Cross-Document Relationship Schemas
class PageAppearance(BaseModel):
    page_number: int
    context_text: Optional[str] = None
    drawing_type: Optional[str] = None


class DocumentAppearance(BaseModel):
    document_id: int
    document_filename: str
    document_title: Optional[str] = None
    pages: List[PageAppearance] = []


class DocumentAppearancesResponse(BaseModel):
    equipment_tag: str
    total_documents: int
    total_pages: int
    documents: List[DocumentAppearance] = []


# Power Flow Tracing Schemas
class PowerFlowNode(BaseModel):
    tag: str
    depth: int
    breaker: Optional[str] = None
    voltage: Optional[str] = None
    wire_size: Optional[str] = None
    load: Optional[str] = None
    document_id: Optional[int] = None
    page_number: Optional[int] = None
    # For upstream nodes
    feeds: Optional[str] = None
    # For downstream nodes
    fed_by: Optional[str] = None


class PowerFlowResponse(BaseModel):
    equipment_tag: str
    upstream_tree: List[PowerFlowNode] = []
    downstream_tree: List[PowerFlowNode] = []
    total_upstream: int = 0
    total_downstream: int = 0


class RelationshipResponse(BaseModel):
    id: int
    source_tag: str
    target_tag: str
    relationship_type: str
    confidence: float

    class Config:
        from_attributes = True


class DetailedConnectionResponse(BaseModel):
    id: int
    document_id: int
    page_number: int
    source_tag: str
    target_tag: str
    category: str  # ELECTRICAL, CONTROL, MECHANICAL, INTERLOCK
    connection_type: Optional[str]
    # Electrical
    voltage: Optional[str]
    breaker: Optional[str]
    wire_size: Optional[str]
    wire_numbers: Optional[str]
    load: Optional[str]
    # Control
    signal_type: Optional[str]
    io_type: Optional[str]
    point_name: Optional[str]
    function: Optional[str]
    # Mechanical
    medium: Optional[str]
    pipe_size: Optional[str]
    pipe_spec: Optional[str]
    inline_devices: Optional[str]
    # General
    confidence: float = 0.7

    class Config:
        from_attributes = True


class EquipmentDetail(EquipmentResponse):
    locations: List[EquipmentLocationResponse] = []
    controls: List[RelationshipResponse] = []
    controlled_by: List[RelationshipResponse] = []
    detailed_connections: List[DetailedConnectionResponse] = []


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
    source_location: Optional[str] = None  # For supplementary docs: "Sheet1:A1-F20"


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


# Multi-Agent Search Schemas
class AgentContribution(BaseModel):
    """Summary of a single agent's contribution to the answer"""
    agent_name: str
    domain: str
    summary: str
    confidence: float
    source_count: int


class MultiAgentSource(BaseModel):
    """Source from multi-agent search"""
    document_name: str
    page_number: str  # Can be page number or location string
    snippet: Optional[str] = None
    equipment_tag: Optional[str] = None
    source_type: str  # pdf, supplementary, graph, equipment_db
    match_type: str
    relevance_score: float = 0.0


class MultiAgentResponse(BaseModel):
    """Response from multi-agent search"""
    query: str
    answer: str
    sources: List[MultiAgentSource]
    agents_used: List[str]
    agent_contributions: List[AgentContribution]
    confidence: float
    was_multi_agent: bool = True
