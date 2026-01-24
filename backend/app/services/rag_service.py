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
