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
