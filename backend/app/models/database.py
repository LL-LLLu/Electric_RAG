from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Index, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()


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
    supplementary_documents = relationship("SupplementaryDocument", back_populates="project", cascade="all, delete-orphan")


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


class Document(Base):
    """Represents an electrical drawing document (PDF)"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
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
    pages_processed = Column(Integer, default=0)  # Track processing progress
    upload_date = Column(DateTime, default=datetime.utcnow)
    processed = Column(Integer, default=0)  # 0=pending, 1=processing, 2=done, -1=error
    processing_error = Column(Text)  # Store error message if failed

    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")
    equipment = relationship("Equipment", back_populates="document")
    project = relationship("Project", back_populates="documents")


class Page(Base):
    """Represents a single page from a drawing"""
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    ocr_text = Column(Text)
    processed_text = Column(Text)
    ai_analysis = Column(Text)  # AI-generated analysis of page content
    ai_equipment_list = Column(Text)  # JSON list of equipment identified by AI
    image_path = Column(String(500))
    embedding = Column(Vector(384))
    drawing_type = Column(String(50), index=True)  # ONE_LINE, PID, CONTROL_SCHEMATIC, WIRING_DIAGRAM, SCHEDULE, GENERAL

    document = relationship("Document", back_populates="pages")
    equipment_locations = relationship("EquipmentLocation", back_populates="page")

    __table_args__ = (
        Index('idx_page_document_number', 'document_id', 'page_number'),
    )


class Equipment(Base):
    """Represents a piece of equipment found in drawings"""
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    tag = Column(String(100), nullable=False, index=True)
    equipment_type = Column(String(100), index=True)
    description = Column(Text)
    manufacturer = Column(String(200))
    model_number = Column(String(200))
    document_id = Column(Integer, ForeignKey("documents.id"))
    primary_page = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="equipment")
    project = relationship("Project", back_populates="equipment")
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
    equipment_data_entries = relationship("EquipmentData", back_populates="equipment")
    aliases = relationship("EquipmentAlias", back_populates="equipment", cascade="all, delete-orphan")
    profile = relationship("EquipmentProfile", back_populates="equipment", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_equipment_project_tag', 'project_id', 'tag', unique=True),
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


class DetailedConnection(Base):
    """Detailed connections between equipment with rich metadata"""
    __tablename__ = "detailed_connections"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    source_tag = Column(String(100), nullable=False, index=True)
    target_tag = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # ELECTRICAL, CONTROL, MECHANICAL, INTERLOCK
    connection_type = Column(String(50))  # FEEDS, CONTROLS, PIPE, DUCT, DRIVES, etc.

    # Electrical details
    voltage = Column(String(50))
    breaker = Column(String(100))
    wire_size = Column(String(50))
    wire_numbers = Column(Text)  # JSON array
    load = Column(String(100))

    # Control details
    signal_type = Column(String(50))  # 4-20mA, 0-10V, 24VDC, dry contact
    io_type = Column(String(20))  # AI, AO, DI, DO
    point_name = Column(String(100))
    function = Column(Text)

    # Mechanical details
    medium = Column(String(100))  # CHW, HW, steam, air, etc.
    pipe_size = Column(String(50))
    pipe_spec = Column(String(100))
    inline_devices = Column(Text)  # JSON array of valves/dampers

    # General
    details_json = Column(Text)  # Full details as JSON for flexibility
    confidence = Column(Float, default=0.7)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_detailed_conn_doc_page', 'document_id', 'page_number'),
        Index('idx_detailed_conn_source', 'source_tag'),
        Index('idx_detailed_conn_target', 'target_tag'),
        Index('idx_detailed_conn_category', 'category'),
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


class SupplementaryDocument(Base):
    """Represents a supplementary document (Excel, Word) uploaded to a project"""
    __tablename__ = "supplementary_documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    document_type = Column(String(20), nullable=False)  # EXCEL, WORD
    content_category = Column(String(50))  # IO_LIST, EQUIPMENT_SCHEDULE, etc.
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    processed = Column(Integer, default=0)  # 0=pending, 1=processing, 2=done, -1=error
    processing_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="supplementary_documents")
    chunks = relationship("SupplementaryChunk", back_populates="document", cascade="all, delete-orphan")
    equipment_data = relationship("EquipmentData", back_populates="document", cascade="all, delete-orphan")


class SupplementaryChunk(Base):
    """Represents a searchable chunk from a supplementary document"""
    __tablename__ = "supplementary_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("supplementary_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    source_location = Column(String(200))  # "Sheet1:A1-F20" or "Section 3.2"
    equipment_tags = Column(Text)  # JSON array
    embedding = Column(Vector(384))

    # Relationships
    document = relationship("SupplementaryDocument", back_populates="chunks")


class EquipmentData(Base):
    """Structured equipment data extracted from supplementary documents"""
    __tablename__ = "equipment_data"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("supplementary_documents.id", ondelete="CASCADE"), nullable=False)
    equipment_tag = Column(String(100), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="SET NULL"))
    match_confidence = Column(Float)
    data_type = Column(String(50), nullable=False)  # IO_POINT, SPECIFICATION, etc.
    data_json = Column(Text, nullable=False)
    source_location = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("SupplementaryDocument", back_populates="equipment_data")
    equipment = relationship("Equipment", back_populates="equipment_data_entries")


class EquipmentAlias(Base):
    """Alternative names/tags for equipment to improve matching"""
    __tablename__ = "equipment_aliases"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(100), nullable=False, index=True)
    source = Column(String(255))
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    equipment = relationship("Equipment", back_populates="aliases")

    __table_args__ = (UniqueConstraint('equipment_id', 'alias', name='uq_equipment_alias'),)


class EquipmentProfile(Base):
    """Consolidated equipment profile aggregating all data sources"""
    __tablename__ = "equipment_profiles"

    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, unique=True)
    profile_json = Column(Text, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)

    # Relationships
    equipment = relationship("Equipment", back_populates="profile")
