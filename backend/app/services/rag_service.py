import os
import logging
from typing import List
from sqlalchemy.orm import Session
import anthropic
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.models.schemas import RAGResponse, SearchResult, QueryType
from app.services.search_service import search_service
from app.services.graph_service import graph_service

logger = logging.getLogger(__name__)

# Retry configuration for LLM API calls
LLM_RETRY_ATTEMPTS = 3
LLM_RETRY_MIN_WAIT = 1  # seconds
LLM_RETRY_MAX_WAIT = 10  # seconds


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

    def query(self, db: Session, query: str, project_id: int = None, limit: int = 25) -> dict:
        """Query with project scope and return dict format for conversations API

        Args:
            db: Database session
            query: Search query
            project_id: Optional project ID to scope search
            limit: Maximum sources to return (default 25 - balanced for quality + comprehensiveness)

        Returns:
            dict with 'answer' and 'sources' keys
        """
        import time

        logger.info(f"RAG Query processing: {query[:100]}...")
        if project_id:
            logger.debug(f"Scoped to project: {project_id}")

        # Extract equipment tags from query for graph-based context
        equipment_tags = graph_service.extract_equipment_from_query(query, db)
        logger.debug(f"Detected equipment tags: {equipment_tags}")

        # Build graph context if equipment tags found
        graph_context = ""
        if equipment_tags:
            logger.debug(f"Building graph context for: {equipment_tags}")
            graph_context = graph_service.build_graph_context(db, equipment_tags, query)
            if graph_context:
                logger.debug(f"Graph context built: {len(graph_context)} chars")

        # Search with project scope - use max_per_document=2 for better cross-document diversity
        search_start = time.time()
        search_response = search_service.search(db, query, limit=limit, project_id=project_id, max_per_document=4)
        logger.info(f"Found {len(search_response.results)} results in {time.time()-search_start:.2f}s")

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
                "document_name": result.document.original_filename,
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

        logger.info(f"RAG processing query: {query[:100]}...")

        # Extract equipment tags for graph-based context
        equipment_tags = graph_service.extract_equipment_from_query(query, db)
        logger.debug(f"Detected equipment tags: {equipment_tags}")

        # Build graph context
        graph_context = ""
        if equipment_tags:
            logger.debug("Building graph context...")
            graph_context = graph_service.build_graph_context(db, equipment_tags, query)
            if graph_context:
                logger.debug(f"Graph context: {len(graph_context)} chars")

        # Search with higher limit for better cross-document coverage
        logger.debug("Step 1: Searching documents...")
        search_start = time.time()
        search_response = search_service.search(db, query, limit=35, max_per_document=8)
        logger.info(f"Found {len(search_response.results)} results in {time.time()-search_start:.2f}s")
        logger.debug(f"Query type: {search_response.query_type}")

        # Get additional context
        additional_context = self._get_additional_context(db, query, search_response.query_type)
        additional_context["graph_context"] = graph_context

        # Build context with adjacent page expansion for top PDF results
        context = self._build_context(search_response.results, additional_context, db)
        logger.debug(f"Context built: {len(context)} chars")

        # Generate answer
        logger.debug(f"Step 2: Generating answer with {self.provider}...")
        if self._has_llm():
            if self.provider == "gemini":
                answer = self._call_gemini(query, context, search_response.query_type)
            else:
                answer = self._call_claude(query, context, search_response.query_type)
        else:
            logger.warning("No LLM available, using fallback")
            answer = self._generate_fallback_answer(query, search_response.results, additional_context)

        logger.info("Answer generated successfully")

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

    def _build_context(self, results: List[SearchResult], additional_context: dict, db: Session = None) -> str:
        """Build context string for LLM, with adjacent page expansion for top PDF results."""
        parts = []

        # Add graph-based context first (most relevant for relationship questions)
        if "graph_context" in additional_context and additional_context["graph_context"]:
            parts.append(additional_context["graph_context"])
            parts.append("")

        # Fetch adjacent page text for top 5 PDF results to give LLM more context
        adjacent_cache = {}
        if db:
            adjacent_cache = self._fetch_adjacent_pages(db, results)

        parts.append("=== RELEVANT DOCUMENT EXCERPTS ===")
        for i, result in enumerate(results, 1):
            # Differentiate between PDF pages and supplementary chunks
            source_type = "[PDF]" if result.match_type in ["exact", "semantic", "keyword", "text_search"] else "[SUPP]"
            parts.append(f"\n[Source {i}] {source_type} Document: {result.document.original_filename}, Page {result.page_number}")

            if result.source_location:
                parts.append(f"Location: {result.source_location}")
            if result.equipment:
                parts.append(f"Equipment: {result.equipment.tag}")
            if result.snippet:
                parts.append(f"Content: {result.snippet}")

            # Add adjacent page context for top PDF results
            adj_key = (result.document.id, result.page_number)
            if adj_key in adjacent_cache:
                adj_text = adjacent_cache[adj_key]
                if adj_text:
                    parts.append(f"Adjacent pages context: {adj_text}")

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

    def _fetch_adjacent_pages(self, db: Session, results: List[SearchResult], top_n: int = 5) -> dict:
        """Fetch text from adjacent pages (N-1, N+1) for top PDF results.

        Returns dict mapping (document_id, page_number) to adjacent page text.
        """
        from app.models.database import Page

        adjacent_cache = {}
        pdf_types = {"exact", "semantic", "keyword", "text_search"}
        pdf_results = [r for r in results if r.match_type in pdf_types][:top_n]

        for result in pdf_results:
            doc_id = result.document.id
            page_num = result.page_number
            adj_parts = []

            for adj_page_num in [page_num - 1, page_num + 1]:
                if adj_page_num < 1:
                    continue
                adj_page = db.query(Page).filter(
                    Page.document_id == doc_id,
                    Page.page_number == adj_page_num
                ).first()

                if adj_page and adj_page.ocr_text:
                    # Truncate to keep context manageable
                    text = adj_page.ocr_text[:800]
                    adj_parts.append(f"[Page {adj_page_num}]: {text}")

            if adj_parts:
                adjacent_cache[(doc_id, page_num)] = " | ".join(adj_parts)

        return adjacent_cache

    def _get_system_prompt(self) -> str:
        """Get the system prompt for LLM calls"""
        return """You are an expert electrical engineering assistant helping users find information in plant electrical drawings and supplementary documents.

Your responsibilities:
1. Answer questions about equipment location, control relationships, power feeds, and wiring
2. When EQUIPMENT GRAPH data is provided, use it as the PRIMARY source for relationship questions
3. Use SUPPLEMENTARY DOCUMENTS (Excel schedules, Word specs) for detailed specifications, IO points, and alarm data
4. Include specific technical details like wire sizes, voltages, signal types, and breaker designations
5. ALWAYS cite ALL relevant documents and page numbers - synthesize information from MULTIPLE documents when available
6. Be precise and technical in your responses
7. If information is not found in the provided context, say so clearly

IMPORTANT - Source Types:
- [PDF] Drawings: Primary source for equipment locations, wiring, and connections
- [SUPP] Supplementary Documents: Excel schedules (IO lists, equipment schedules) and Word docs (sequences of operation, specs)

FORMATTING RULES (STRICT):
1. **Executive Summary**: Start with a direct, high-level answer (2-3 sentences).
2. **Tables**: Use Markdown tables for lists of equipment, technical specifications, and connections.
   - Connections Table: | Source | Connection Type | Target | Details | Reference |
   - Specifications Table: | Parameter | Value | Reference |
3. **Structure**: Use clear headings (##) for different sections (e.g., ## Location, ## Specifications, ## Connections).
4. **Bolding**: **Bold** all equipment tags, key voltages (e.g., **480V**), and critical values.
5. **Readability**: Use bullet points for lists. Avoid long paragraphs.
6. **Citations**: Cite every fact using [Source X] format.
7. **Document References**: End with a dedicated section listing the full document names and page numbers referenced.

For relationship questions (what feeds X, what controls Y, etc.):
- Use a table to show the connections clearly
- Include specific details like voltage, wire size, breaker, signal type
- Explain the hierarchy (e.g., "M-1 is fed from MCC-2")

For specification questions (alarms, IO points, setpoints):
- Use tables to list IO points and Alarms
- Include columns for Tag, Description, Type/Category, and Source"""

    def _get_user_prompt(self, query: str, context: str) -> str:
        """Get the user prompt for LLM calls"""
        return f"""Based on the following context from our electrical drawing database, please answer this question:

Question: {query}

{context}

Provide a clear, technical answer with document references."""

    @retry(
        stop=stop_after_attempt(LLM_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=LLM_RETRY_MIN_WAIT, max=LLM_RETRY_MAX_WAIT),
        retry=retry_if_exception_type((anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError)),
        before_sleep=lambda retry_state: logger.warning(f"Claude API call failed, retrying in {retry_state.next_action.sleep} seconds... (attempt {retry_state.attempt_number}/{LLM_RETRY_ATTEMPTS})")
    )
    def _call_claude_with_retry(self, system_prompt: str, user_prompt: str) -> str:
        """Make Claude API call with retry logic"""
        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text

    def _call_claude(self, query: str, context: str, query_type: QueryType) -> str:
        """Call Claude API to generate answer"""
        import time
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(query, context)

        logger.info(f"Calling Claude API for query: {query[:100]}...")
        logger.debug(f"Context length: {len(context)} chars")

        try:
            start_time = time.time()
            answer = self._call_claude_with_retry(system_prompt, user_prompt)
            elapsed = time.time() - start_time

            logger.info(f"Claude response received in {elapsed:.2f}s ({len(answer)} chars)")
            return answer
        except Exception as e:
            logger.error(f"Claude API error after {LLM_RETRY_ATTEMPTS} retries: {e}")
            return self._generate_fallback_answer(query, [], {})

    @retry(
        stop=stop_after_attempt(LLM_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=LLM_RETRY_MIN_WAIT, max=LLM_RETRY_MAX_WAIT),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        before_sleep=lambda retry_state: logger.warning(f"Gemini API call failed, retrying in {retry_state.next_action.sleep} seconds... (attempt {retry_state.attempt_number}/{LLM_RETRY_ATTEMPTS})")
    )
    def _call_gemini_with_retry(self, prompt: str) -> str:
        """Make Gemini API call with retry logic"""
        response = self.gemini_model.generate_content(prompt)
        return response.text

    def _call_gemini(self, query: str, context: str, query_type: QueryType) -> str:
        """Call Gemini API to generate answer"""
        import time
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(query, context)

        logger.info(f"Calling Gemini API for query: {query[:100]}...")
        logger.debug(f"Context length: {len(context)} chars")

        try:
            start_time = time.time()
            answer = self._call_gemini_with_retry(f"{system_prompt}\n\n{user_prompt}")
            elapsed = time.time() - start_time

            logger.info(f"Gemini response received in {elapsed:.2f}s ({len(answer)} chars)")
            return answer
        except Exception as e:
            logger.error(f"Gemini API error after {LLM_RETRY_ATTEMPTS} retries: {e}")
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
