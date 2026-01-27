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
