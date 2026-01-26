from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.database import Equipment, EquipmentRelationship, Document, DetailedConnection, EquipmentLocation, Page
from app.models.schemas import (
    EquipmentResponse, EquipmentDetail, RelationshipCreate, DetailedConnectionResponse,
    DocumentAppearancesResponse, DocumentAppearance, PageAppearance,
    PowerFlowResponse, PowerFlowNode
)

router = APIRouter()


@router.get("/", response_model=List[EquipmentResponse])
async def list_equipment(
    skip: int = 0,
    limit: int = 100,
    equipment_type: str = None,
    search: str = None,
    project_id: int = None,
    document_id: int = None,
    db: Session = Depends(get_db)
):
    """List all equipment with optional filtering"""
    query = db.query(Equipment)

    if project_id:
        query = query.filter(Equipment.project_id == project_id)

    if document_id:
        query = query.filter(Equipment.document_id == document_id)

    if equipment_type:
        query = query.filter(Equipment.equipment_type == equipment_type)

    if search:
        query = query.filter(Equipment.tag.ilike(f"%{search}%"))

    equipment = query.offset(skip).limit(limit).all()
    return equipment


@router.get("/by-project/{project_id}", response_model=List[EquipmentResponse])
async def list_equipment_by_project(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    equipment_type: str = None,
    search: str = None,
    db: Session = Depends(get_db)
):
    """List equipment for a specific project (via document relationship)"""
    # Join with Document to get equipment from documents in this project
    query = db.query(Equipment).join(
        Document, Equipment.document_id == Document.id
    ).filter(Document.project_id == project_id)

    if equipment_type:
        query = query.filter(Equipment.equipment_type == equipment_type)

    if search:
        query = query.filter(Equipment.tag.ilike(f"%{search}%"))

    equipment = query.offset(skip).limit(limit).all()
    return equipment


@router.get("/by-document/{document_id}", response_model=List[EquipmentResponse])
async def list_equipment_by_document(
    document_id: int,
    skip: int = 0,
    limit: int = 100,
    equipment_type: str = None,
    search: str = None,
    db: Session = Depends(get_db)
):
    """List equipment for a specific document"""
    query = db.query(Equipment).filter(Equipment.document_id == document_id)

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
            "document_id": doc.id,
            "document_filename": doc.original_filename or doc.filename,
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

    # Get detailed connections where this equipment is source or target
    detailed_connections = db.query(DetailedConnection).filter(
        (func.upper(DetailedConnection.source_tag) == tag.upper()) |
        (func.upper(DetailedConnection.target_tag) == tag.upper())
    ).all()

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
        controlled_by=controlled_by,
        detailed_connections=detailed_connections
    )


@router.get("/{tag}/documents", response_model=DocumentAppearancesResponse)
async def get_equipment_documents(tag: str, db: Session = Depends(get_db)):
    """Get all documents where this equipment appears, grouped by document with page details"""
    equipment = db.query(Equipment).filter(
        func.upper(Equipment.tag) == tag.upper()
    ).first()

    if not equipment:
        raise HTTPException(status_code=404, detail=f"Equipment {tag} not found")

    # Get all locations for this equipment
    locations = db.query(EquipmentLocation).filter(
        EquipmentLocation.equipment_id == equipment.id
    ).all()

    # Group by document
    doc_map: dict[int, dict] = {}
    for loc in locations:
        page = loc.page
        doc = page.document

        if doc.id not in doc_map:
            doc_map[doc.id] = {
                "document_id": doc.id,
                "document_filename": doc.original_filename or doc.filename,
                "document_title": doc.title,
                "pages": []
            }

        doc_map[doc.id]["pages"].append(PageAppearance(
            page_number=page.page_number,
            context_text=loc.context_text,
            drawing_type=page.drawing_type
        ))

    # Sort pages within each document
    documents = []
    for doc_data in doc_map.values():
        doc_data["pages"] = sorted(doc_data["pages"], key=lambda p: p.page_number)
        documents.append(DocumentAppearance(**doc_data))

    # Sort documents by filename
    documents = sorted(documents, key=lambda d: d.document_filename)

    return DocumentAppearancesResponse(
        equipment_tag=equipment.tag,
        total_documents=len(documents),
        total_pages=sum(len(d.pages) for d in documents),
        documents=documents
    )


@router.get("/{tag}/power-flow", response_model=PowerFlowResponse)
async def get_power_flow(
    tag: str,
    max_depth: int = Query(default=10, ge=1, le=20, description="Maximum traversal depth"),
    db: Session = Depends(get_db)
):
    """
    Trace the full power chain for an equipment tag.

    Returns the complete upstream (what feeds this) and downstream (what this feeds)
    power hierarchy using BFS traversal. Supports multi-branch power distribution.
    """
    from app.services.graph_service import graph_service

    # Verify equipment exists
    equipment = db.query(Equipment).filter(
        func.upper(Equipment.tag) == tag.upper()
    ).first()

    # Even if equipment doesn't exist in equipment table, try to find it in connections
    if not equipment:
        # Check if tag exists in detailed_connections
        exists_in_connections = db.query(DetailedConnection).filter(
            (func.upper(DetailedConnection.source_tag) == tag.upper()) |
            (func.upper(DetailedConnection.target_tag) == tag.upper())
        ).first()

        if not exists_in_connections:
            raise HTTPException(status_code=404, detail=f"Equipment {tag} not found")

    # Get full power flow using BFS traversal
    power_flow = graph_service.get_full_power_flow(db, tag, max_depth)

    # Convert to response model
    upstream_nodes = [PowerFlowNode(**node) for node in power_flow["upstream_tree"]]
    downstream_nodes = [PowerFlowNode(**node) for node in power_flow["downstream_tree"]]

    return PowerFlowResponse(
        equipment_tag=tag,
        upstream_tree=upstream_nodes,
        downstream_tree=downstream_nodes,
        total_upstream=power_flow["total_upstream"],
        total_downstream=power_flow["total_downstream"]
    )


@router.get("/{tag}/graph")
async def get_equipment_graph(
    tag: str,
    depth: int = Query(default=1, ge=1, le=3, description="Graph traversal depth"),
    db: Session = Depends(get_db)
):
    """Get graph visualization data for an equipment tag.

    Returns nodes and edges for visualization with vis.js or similar.
    """
    from app.services.graph_service import graph_service

    # Get connections for the equipment
    connections = graph_service.get_equipment_connections(db, tag)

    nodes = []
    edges = []
    seen_nodes = set()

    # Add center node
    center_tag = tag.upper()
    node_type = "unknown"
    if connections.get("equipment_info"):
        node_type = connections["equipment_info"].get("type", "unknown")

    nodes.append({
        "id": center_tag,
        "label": center_tag,
        "type": node_type,
        "isCenter": True
    })
    seen_nodes.add(center_tag)

    # Helper to add node if not seen
    def add_node(node_tag: str, conn_details: dict = None):
        if node_tag.upper() not in seen_nodes:
            seen_nodes.add(node_tag.upper())
            nodes.append({
                "id": node_tag.upper(),
                "label": node_tag,
                "type": conn_details.get("category", "unknown") if conn_details else "unknown",
                "isCenter": False
            })

    # Add nodes and edges for each relationship type
    for feed in connections.get("feeds_from", []):
        add_node(feed["tag"], feed.get("details"))
        edges.append({
            "from": feed["tag"].upper(),
            "to": center_tag,
            "type": "feeds",
            "label": "FEEDS",
            "details": feed.get("details", {})
        })

    for feed in connections.get("feeds_to", []):
        add_node(feed["tag"], feed.get("details"))
        edges.append({
            "from": center_tag,
            "to": feed["tag"].upper(),
            "type": "feeds",
            "label": "FEEDS",
            "details": feed.get("details", {})
        })

    for ctrl in connections.get("controlled_by", []):
        add_node(ctrl["tag"], ctrl.get("details"))
        edges.append({
            "from": ctrl["tag"].upper(),
            "to": center_tag,
            "type": "controls",
            "label": "CONTROLS",
            "details": ctrl.get("details", {})
        })

    for ctrl in connections.get("controls", []):
        add_node(ctrl["tag"], ctrl.get("details"))
        edges.append({
            "from": center_tag,
            "to": ctrl["tag"].upper(),
            "type": "controls",
            "label": "CONTROLS",
            "details": ctrl.get("details", {})
        })

    for prot in connections.get("protected_by", []):
        add_node(prot["tag"], prot.get("details"))
        edges.append({
            "from": prot["tag"].upper(),
            "to": center_tag,
            "type": "protects",
            "label": "PROTECTS",
            "details": prot.get("details", {})
        })

    for prot in connections.get("protects", []):
        add_node(prot["tag"], prot.get("details"))
        edges.append({
            "from": center_tag,
            "to": prot["tag"].upper(),
            "type": "protects",
            "label": "PROTECTS",
            "details": prot.get("details", {})
        })

    for mon in connections.get("monitored_by", []):
        add_node(mon["tag"], mon.get("details"))
        edges.append({
            "from": mon["tag"].upper(),
            "to": center_tag,
            "type": "monitors",
            "label": "MONITORS",
            "details": mon.get("details", {})
        })

    for mon in connections.get("monitors", []):
        add_node(mon["tag"], mon.get("details"))
        edges.append({
            "from": center_tag,
            "to": mon["tag"].upper(),
            "type": "monitors",
            "label": "MONITORS",
            "details": mon.get("details", {})
        })

    for conn in connections.get("connected_to", []):
        add_node(conn["tag"], conn.get("details"))
        edges.append({
            "from": center_tag,
            "to": conn["tag"].upper(),
            "type": "mechanical",
            "label": "CONNECTS",
            "details": conn.get("details", {})
        })

    for drv in connections.get("driven_by", []):
        add_node(drv["tag"], drv.get("details"))
        edges.append({
            "from": drv["tag"].upper(),
            "to": center_tag,
            "type": "drives",
            "label": "DRIVES",
            "details": drv.get("details", {})
        })

    for drv in connections.get("drives", []):
        add_node(drv["tag"], drv.get("details"))
        edges.append({
            "from": center_tag,
            "to": drv["tag"].upper(),
            "type": "drives",
            "label": "DRIVES",
            "details": drv.get("details", {})
        })

    return {
        "center_tag": tag,
        "nodes": nodes,
        "edges": edges,
        "equipment_info": connections.get("equipment_info")
    }


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
