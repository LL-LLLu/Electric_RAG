import os
import logging
from typing import List
from sqlalchemy.orm import Session
import anthropic
import google.generativeai as genai

from app.models.schemas import RAGResponse, SearchResult, QueryType
from app.services.search_service import search_service
from app.services.graph_service import graph_service

logger = logging.getLogger(__name__)


class RAGService:
    """Generate natural language answers using Claude or Gemini"""

    def __init__(self):
        self.provider = os.environ.get("LLM_PROVIDER", "claude").lower()
        self.anthropic_client = None
        self.gemini_model = None

        if self.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
            else:
                logger.warning("ANTHROPIC_API_KEY not set, RAG responses will be limited")
        elif self.provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel("gemini-3-flash-preview")
            else:
                logger.warning("GEMINI_API_KEY not set, RAG responses will be limited")
        else:
            logger.warning(f"Unknown LLM_PROVIDER: {self.provider}, defaulting to fallback")

    def _has_llm(self) -> bool:
        """Check if any LLM client is available"""
        return self.anthropic_client is not None or self.gemini_model is not None

    def query(self, db: Session, query: str, project_id: int = None, limit: int = 20) -> dict:
        """Query with project scope and return dict format for conversations API

        Args:
            db: Database session
            query: Search query
            project_id: Optional project ID to scope search
            limit: Maximum sources to return (default 20 for better cross-document coverage)

        Returns:
            dict with 'answer' and 'sources' keys
        """
        import time

        print(f"\n{'='*60}")
        print(f"[RAG Query] Processing: {query}")
        if project_id:
            print(f"[RAG Query] Scoped to project: {project_id}")
        print(f"{'='*60}")

        # Extract equipment tags from query for graph-based context
        equipment_tags = graph_service.extract_equipment_from_query(query, db)
        print(f"[RAG Query] Detected equipment tags: {equipment_tags}")

        # Build graph context if equipment tags found
        graph_context = ""
        if equipment_tags:
            print(f"[RAG Query] Building graph context for: {equipment_tags}")
            graph_context = graph_service.build_graph_context(db, equipment_tags, query)
            if graph_context:
                print(f"[RAG Query] Graph context built: {len(graph_context)} chars")

        # Search with project scope - use max_per_document=2 for better cross-document diversity
        search_start = time.time()
        search_response = search_service.search(db, query, limit=limit, project_id=project_id, max_per_document=2)
        print(f"[RAG Query] Found {len(search_response.results)} results in {time.time()-search_start:.2f}s")

        # Build context with graph data
        context = self._build_context(search_response.results, {"graph_context": graph_context})

        # Generate answer
        if self._has_llm():
            if self.provider == "gemini":
                answer = self._call_gemini(query, context, search_response.query_type)
            else:
                answer = self._call_claude(query, context, search_response.query_type)
        else:
            answer = self._generate_fallback_answer(query, search_response.results, {})

        # Build sources list in expected format
        sources = []
        for result in search_response.results:
            sources.append({
                "document_id": result.document.id,
                "document_name": result.document.filename,
                "page_number": result.page_number,
                "snippet": result.snippet,
                "bbox": None,  # TODO: Add bbox support when available
                "equipment_tag": result.equipment.tag if result.equipment else None,
                "source_location": result.source_location,  # For supplementary docs (Excel cell, Word section)
                "match_type": result.match_type  # For frontend to differentiate PDF vs supplementary
            })

        return {
            "answer": answer,
            "sources": sources
        }

    def generate_answer(self, db: Session, query: str) -> RAGResponse:
        """Generate an answer using search results and LLM"""
        import time

        print(f"\n{'='*60}")
        print(f"[RAG] Processing query: {query}")
        print(f"{'='*60}")

        # Extract equipment tags for graph-based context
        equipment_tags = graph_service.extract_equipment_from_query(query, db)
        print(f"[RAG] Detected equipment tags: {equipment_tags}")

        # Build graph context
        graph_context = ""
        if equipment_tags:
            print(f"[RAG] Building graph context...")
            graph_context = graph_service.build_graph_context(db, equipment_tags, query)
            if graph_context:
                print(f"[RAG] Graph context: {len(graph_context)} chars")

        # Search with higher limit for better cross-document coverage
        print(f"[RAG] Step 1: Searching documents...")
        search_start = time.time()
        search_response = search_service.search(db, query, limit=20, max_per_document=2)
        print(f"[RAG] Found {len(search_response.results)} results in {time.time()-search_start:.2f}s")
        print(f"[RAG] Query type: {search_response.query_type}")

        # Get additional context
        additional_context = self._get_additional_context(db, query, search_response.query_type)
        additional_context["graph_context"] = graph_context

        # Build context
        context = self._build_context(search_response.results, additional_context)
        print(f"[RAG] Context built: {len(context)} chars")

        # Generate answer
        print(f"[RAG] Step 2: Generating answer with {self.provider}...")
        if self._has_llm():
            if self.provider == "gemini":
                answer = self._call_gemini(query, context, search_response.query_type)
            else:
                answer = self._call_claude(query, context, search_response.query_type)
        else:
            print(f"[RAG] No LLM available, using fallback")
            answer = self._generate_fallback_answer(query, search_response.results, additional_context)

        print(f"[RAG] Answer generated successfully")
        print(f"{'='*60}\n")

        return RAGResponse(
            query=query,
            answer=answer,
            sources=search_response.results,
            query_type=search_response.query_type,
            confidence=0.9 if self._has_llm() else 0.6
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

        # Add graph-based context first (most relevant for relationship questions)
        if "graph_context" in additional_context and additional_context["graph_context"]:
            parts.append(additional_context["graph_context"])
            parts.append("")

        parts.append("=== RELEVANT DOCUMENT EXCERPTS ===")
        for i, result in enumerate(results, 1):
            # Differentiate between PDF pages and supplementary chunks
            source_type = "📄" if result.match_type in ["exact", "semantic", "keyword", "text_search"] else "📊"
            parts.append(f"\n[Source {i}] {source_type} Document: {result.document.filename}, Page {result.page_number}")

            if result.source_location:
                parts.append(f"Location: {result.source_location}")
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

    def _get_system_prompt(self) -> str:
        """Get the system prompt for LLM calls"""
        return """You are an electrical engineering assistant helping users find information in plant electrical drawings and supplementary documents.

Your responsibilities:
1. Answer questions about equipment location, control relationships, power feeds, and wiring
2. When EQUIPMENT GRAPH data is provided, use it as the PRIMARY source for relationship questions
3. Use SUPPLEMENTARY DOCUMENTS (Excel schedules, Word specs) for detailed specifications, IO points, and alarm data
4. Include specific technical details like wire sizes, voltages, signal types, and breaker designations
5. ALWAYS cite ALL relevant documents and page numbers - synthesize information from MULTIPLE documents when available
6. Be precise and technical in your responses
7. If information is not found in the provided context, say so clearly

IMPORTANT - Source Types:
- 📄 PDF Drawings: Primary source for equipment locations, wiring, and connections
- 📊 Supplementary Documents: Excel schedules (IO lists, equipment schedules) and Word docs (sequences of operation, specs)

For relationship questions (what feeds X, what controls Y, etc.):
- Use the EQUIPMENT GRAPH section to provide detailed answers
- Include connection details like voltage, wire size, breaker, signal type
- Explain the control/power hierarchy clearly

For specification questions (alarms, IO points, setpoints):
- Prioritize data from Excel IO lists and equipment schedules
- Include specific values and categories

Format your response clearly with:
- Direct answer to the question with technical details
- Specific connection information (voltage, wire size, breaker, signal type)
- ALL document references (Document: X, Page: Y or Location: Z) from every relevant source"""

    def _get_user_prompt(self, query: str, context: str) -> str:
        """Get the user prompt for LLM calls"""
        return f"""Based on the following context from our electrical drawing database, please answer this question:

Question: {query}

{context}

Provide a clear, technical answer with document references."""

    def _call_claude(self, query: str, context: str, query_type: QueryType) -> str:
        """Call Claude API to generate answer"""
        import time
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(query, context)

        print(f"\n[LLM] Calling Claude API...")
        print(f"[LLM] Query: {query[:100]}...")
        print(f"[LLM] Context length: {len(context)} chars")

        try:
            start_time = time.time()
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            elapsed = time.time() - start_time
            answer = response.content[0].text

            print(f"[LLM] Claude response received in {elapsed:.2f}s")
            print(f"[LLM] Response length: {len(answer)} chars")
            print(f"[LLM] Response preview: {answer[:200]}...")

            return answer
        except Exception as e:
            print(f"[LLM] Claude API ERROR: {e}")
            logger.error(f"Claude API error: {e}")
            return self._generate_fallback_answer(query, [], {})

    def _call_gemini(self, query: str, context: str, query_type: QueryType) -> str:
        """Call Gemini API to generate answer"""
        import time
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(query, context)

        print(f"\n[LLM] Calling Gemini API...")
        print(f"[LLM] Query: {query[:100]}...")
        print(f"[LLM] Context length: {len(context)} chars")

        try:
            start_time = time.time()
            response = self.gemini_model.generate_content(
                f"{system_prompt}\n\n{user_prompt}"
            )
            elapsed = time.time() - start_time
            answer = response.text

            print(f"[LLM] Gemini response received in {elapsed:.2f}s")
            print(f"[LLM] Response length: {len(answer)} chars")
            print(f"[LLM] Response preview: {answer[:200]}...")

            return answer
        except Exception as e:
            print(f"[LLM] Gemini API ERROR: {e}")
            logger.error(f"Gemini API error: {e}")
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
