from typing import List
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.auth import require_api_key
from app.models.schemas import SearchRequest, SearchResponse, RAGResponse, MultiAgentResponse
from app.services.search_service import search_service
from app.services.rag_service import rag_service
from app.services.multi_agent_search_service import multi_agent_search_service
from app.api.limiter import limiter

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Search for equipment, documents, or general queries"""
    return search_service.search(db, q, limit)


@router.post("/ask", response_model=RAGResponse)
@limiter.limit("10/minute")
async def ask_question(
    request: Request,
    search_req: SearchRequest,
    db: Session = Depends(get_db)
):
    """Ask a natural language question and get an AI-generated answer"""
    return rag_service.generate_answer(db, search_req.query)


@router.post("/ask/multi-agent")
@limiter.limit("10/minute")
async def ask_question_multi_agent(
    request: Request,
    search_req: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Ask a complex question using multi-agent search.

    This endpoint uses multiple specialized agents to gather comprehensive
    information across different domains (specs, relationships, IO, alarms, sequences).
    Best for complex queries that span multiple aspects of equipment or systems.
    """
    response = multi_agent_search_service.query(
        db=db,
        query=search_req.query,
        project_id=None  # Global search
    )

    # Convert dataclass to dict for JSON serialization
    return {
        "query": response.query,
        "answer": response.answer,
        "sources": response.sources,
        "agents_used": response.agents_used,
        "agent_contributions": [
            {
                "agent_name": c.agent_name,
                "domain": c.domain,
                "summary": c.summary,
                "confidence": c.confidence,
                "source_count": c.source_count
            }
            for c in response.agent_contributions
        ],
        "confidence": response.confidence,
        "was_multi_agent": response.was_multi_agent
    }


@router.post("/ask/smart")
@limiter.limit("10/minute")
async def ask_question_smart(
    request: Request,
    search_req: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Smart routing: Automatically decide between single-agent and multi-agent search.

    Uses query complexity analysis to determine the best approach:
    - Simple queries: Fast single-agent response
    - Complex queries: Comprehensive multi-agent response
    """
    # First, do a quick search to analyze result diversity
    initial_results = search_service.search(db, search_req.query, limit=20)

    # Decide routing
    if multi_agent_search_service.should_use_multi_agent(search_req.query, initial_results.results):
        # Use multi-agent for complex queries
        response = multi_agent_search_service.query(db, search_req.query)
        return {
            "query": response.query,
            "answer": response.answer,
            "sources": response.sources,
            "agents_used": response.agents_used,
            "agent_contributions": [
                {
                    "agent_name": c.agent_name,
                    "domain": c.domain,
                    "summary": c.summary,
                    "confidence": c.confidence,
                    "source_count": c.source_count
                }
                for c in response.agent_contributions
            ],
            "confidence": response.confidence,
            "was_multi_agent": True
        }
    else:
        # Use single-agent for simple queries
        rag_response = rag_service.generate_answer(db, search_req.query)
        return {
            "query": rag_response.query,
            "answer": rag_response.answer,
            "sources": [
                {
                    "document_name": s.document.filename,
                    "page_number": str(s.page_number),
                    "snippet": s.snippet,
                    "equipment_tag": s.equipment.tag if s.equipment else None,
                    "source_type": "pdf" if s.match_type in ["exact", "semantic", "keyword"] else "supplementary",
                    "match_type": s.match_type,
                    "relevance_score": s.relevance_score
                }
                for s in rag_response.sources
            ],
            "agents_used": ["rag_service"],
            "agent_contributions": [],
            "confidence": rag_response.confidence,
            "was_multi_agent": False
        }


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
