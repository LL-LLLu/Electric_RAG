import json
import os
import re
import time
import logging
from datetime import datetime
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func

import anthropic
import google.generativeai as genai

from app.models.database import Document, Page, Equipment, EquipmentLocation, EquipmentRelationship, SupplementaryChunk, EquipmentData, SupplementaryDocument, EquipmentAlias
from app.models.schemas import QueryType, SearchResult, SearchResponse, DocumentResponse, EquipmentBrief
from app.services.embedding_service import embedding_service
from app.services.extraction_service import extraction_service

logger = logging.getLogger(__name__)

# Query rewriting prompt
QUERY_REWRITE_PROMPT = """You are a search query optimizer for an industrial equipment documentation system.

Your task is to rewrite the user's query to improve search results. The system contains:
- Electrical drawings (one-line diagrams, wiring diagrams, control schematics)
- Equipment schedules (Excel files with specs, IO lists, alarm lists)
- Sequences of operation (Word documents)

RULES:
1. Extract and normalize equipment tags (e.g., "supply fan" → "SF", "air handling unit" → "AHU")
2. Add common variations of equipment tags (e.g., "VFD-101" → also search "VFD101", "VFD 101")
3. Add relevant technical terms based on query intent
4. Fix obvious typos
5. Keep the query focused - don't add unrelated terms
6. For relationship queries, include terms like "feeds", "powers", "controls", "upstream", "downstream"
7. For specification queries, include terms like "HP", "kW", "voltage", "rating", "spec"
8. For alarm queries, include terms like "alarm", "trip", "setpoint", "interlock"
9. For IO queries, include terms like "IO", "point", "signal", "AI", "AO", "DI", "DO"

OUTPUT FORMAT:
Return ONLY the rewritten query on a single line. No explanations, no quotes, no prefixes.

EXAMPLES:
User: "horsepower of the supply fan"
Output: SF supply fan HP horsepower rating specification motor

User: "what controls ahu-1"
Output: AHU-1 AHU1 controls controlled by controller PLC BAS signal

User: "alarms for pump 101"
Output: P-101 P101 pump 101 alarm alarms trip setpoint interlock fault

User: "where is vfd101 located"
Output: VFD-101 VFD101 VFD 101 location drawing page sheet

User: "io points for the chiller"
Output: chiller CH IO points signals AI AO DI DO analog digital input output"""


class SearchService:
    """Hybrid search: exact match + semantic + keyword with query rewriting"""

    def __init__(self):
        """Initialize search service with LLM client for query rewriting"""
        self.provider = os.environ.get("LLM_PROVIDER", "claude").lower()
        self.anthropic_client = None
        self.gemini_model = None
        self._init_llm_client()

    def _init_llm_client(self):
        """Initialize LLM client for query rewriting"""
        if self.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        elif self.provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")

    def _has_llm(self) -> bool:
        """Check if LLM is available for query rewriting"""
        return self.anthropic_client is not None or self.gemini_model is not None

    def rewrite_query(self, original_query: str) -> Tuple[str, str]:
        """
        Use LLM to rewrite/expand the query for better search results.

        Args:
            original_query: The user's original query

        Returns:
            Tuple of (rewritten_query, original_query)
            If LLM fails, returns (original_query, original_query)
        """
        if not self._has_llm():
            return original_query, original_query

        try:
            user_prompt = f"User query: {original_query}"

            if self.provider == "gemini" and self.gemini_model:
                response = self.gemini_model.generate_content(
                    f"{QUERY_REWRITE_PROMPT}\n\n{user_prompt}",
                    generation_config={"max_output_tokens": 100, "temperature": 0.1}
                )
                rewritten = response.text.strip()
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=100,
                    temperature=0,
                    system=QUERY_REWRITE_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                rewritten = response.content[0].text.strip()
            else:
                return original_query, original_query

            # Clean up the response - remove quotes, newlines, etc.
            rewritten = rewritten.replace('"', '').replace("'", "").strip()
            rewritten = ' '.join(rewritten.split())  # Normalize whitespace

            # Sanity check - if rewritten is empty or too short, use original
            if len(rewritten) < 3:
                return original_query, original_query

            logger.debug(f"[SEARCH] Query rewritten: '{original_query}' → '{rewritten}'")
            return rewritten, original_query

        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}")
            return original_query, original_query

    def classify_query(self, query: str) -> QueryType:
        """Determine the type of query"""
        query_lower = query.lower()

        has_equipment_tag = bool(re.search(r'\b[A-Z]{2,4}-?\d{2,4}\b', query, re.IGNORECASE))

        if any(word in query_lower for word in ['where is', 'find', 'locate', 'which drawing', 'which page']):
            return QueryType.EQUIPMENT_LOOKUP

        if any(word in query_lower for word in ['control', 'controls', 'controlled by', 'what controls']):
            return QueryType.RELATIONSHIP

        if any(word in query_lower for word in ['upstream', 'downstream', 'feeds', 'powered by', 'powers']):
            return QueryType.UPSTREAM_DOWNSTREAM

        if any(word in query_lower for word in ['wire', 'cable', 'conductor', 'w-']):
            return QueryType.WIRE_TRACE

        if has_equipment_tag:
            return QueryType.EQUIPMENT_LOOKUP

        return QueryType.GENERAL

    def expand_equipment_tags_with_aliases(self, db: Session, tags: List[str], project_id: int = None) -> List[str]:
        """
        Expand equipment tags by looking up aliases.

        For each tag:
        1. Find if it's a canonical equipment tag -> get all its aliases
        2. Find if it's an alias -> get the canonical tag and all other aliases

        Returns a deduplicated list of all tags to search for.
        """
        expanded_tags = set(tags)  # Start with original tags

        for tag in tags:
            tag_upper = tag.upper()

            # 1. Check if this tag is a canonical equipment tag
            equipment_query = db.query(Equipment).filter(
                func.upper(Equipment.tag) == tag_upper
            )
            if project_id:
                equipment_query = equipment_query.filter(Equipment.project_id == project_id)
            equipment = equipment_query.first()

            if equipment:
                # Get all aliases for this equipment
                aliases = db.query(EquipmentAlias).filter(
                    EquipmentAlias.equipment_id == equipment.id
                ).all()
                for alias in aliases:
                    expanded_tags.add(alias.alias.upper())

            # 2. Check if this tag is an alias
            alias_matches = db.query(EquipmentAlias).filter(
                func.upper(EquipmentAlias.alias) == tag_upper
            ).all()

            for alias_match in alias_matches:
                # Get the canonical equipment
                eq = db.query(Equipment).filter(Equipment.id == alias_match.equipment_id).first()
                if eq:
                    expanded_tags.add(eq.tag.upper())
                    # Also get all other aliases for this equipment
                    other_aliases = db.query(EquipmentAlias).filter(
                        EquipmentAlias.equipment_id == eq.id
                    ).all()
                    for other_alias in other_aliases:
                        expanded_tags.add(other_alias.alias.upper())

        # Return as list, preserving original tags first
        result = list(tags)  # Original tags first
        for t in expanded_tags:
            if t not in [x.upper() for x in result]:
                result.append(t)

        return result

    def _detect_equipment_type_query(self, query: str) -> str:
        """
        Detect if query is asking for all equipment of a specific type.
        Returns the equipment type abbreviation if detected, None otherwise.

        Examples:
        - "list all RTUs" -> "RTU"
        - "what are the pumps in the project" -> "PUMP"
        - "show me all VFDs" -> "VFD"
        """
        query_lower = query.lower()

        # Check for "list all" or "show all" or "what are the" patterns
        list_patterns = [
            r'list\s+(?:all\s+)?(?:the\s+)?(\w+)',
            r'show\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(\w+)',
            r'what\s+(?:are\s+)?(?:all\s+)?(?:the\s+)?(\w+)',
            r'find\s+(?:all\s+)?(?:the\s+)?(\w+)',
            r'all\s+(?:the\s+)?(\w+)\s+in',
        ]

        # Equipment type mappings (plural/singular to type)
        type_mappings = {
            'rtu': 'RTU', 'rtus': 'RTU', 'remote terminal unit': 'RTU', 'remote terminal units': 'RTU',
            'pump': 'PUMP', 'pumps': 'PUMP',
            'vfd': 'VFD', 'vfds': 'VFD', 'variable frequency drive': 'VFD', 'drives': 'VFD',
            'motor': 'MOTOR', 'motors': 'MOTOR',
            'fan': 'FAN', 'fans': 'FAN', 'ahu': 'FAN', 'ahus': 'FAN', 'air handler': 'FAN',
            'breaker': 'BREAKER', 'breakers': 'BREAKER',
            'panel': 'PANEL', 'panels': 'PANEL', 'mcc': 'PANEL', 'mccs': 'PANEL',
            'plc': 'PLC', 'plcs': 'PLC', 'controller': 'PLC', 'controllers': 'PLC',
            'transformer': 'TRANSFORMER', 'transformers': 'TRANSFORMER', 'xfmr': 'TRANSFORMER',
            'sensor': 'SENSOR', 'sensors': 'SENSOR',
            'valve': 'VALVE', 'valves': 'VALVE',
            'rio': 'RIO', 'rios': 'RIO', 'remote io': 'RIO', 'remote i/o': 'RIO',
        }

        for pattern in list_patterns:
            match = re.search(pattern, query_lower)
            if match:
                potential_type = match.group(1).strip()
                if potential_type in type_mappings:
                    return type_mappings[potential_type]

        # Direct check for equipment type mentions
        for term, eq_type in type_mappings.items():
            if term in query_lower:
                # Make sure it's a "list all" context
                if any(p in query_lower for p in ['list', 'all', 'show', 'find', 'what are']):
                    return eq_type

        return None

    def _search_equipment_by_type(self, db: Session, equipment_type: str, limit: int = 50, project_id: int = None) -> List[SearchResult]:
        """
        Search for all equipment of a specific type.
        Returns equipment with their locations from the database.
        """
        results = []

        # Query equipment by type or by tag pattern
        eq_query = db.query(Equipment).filter(
            or_(
                Equipment.equipment_type == equipment_type,
                Equipment.tag.ilike(f'{equipment_type}%'),
                Equipment.tag.ilike(f'%{equipment_type}%')
            )
        )
        if project_id is not None:
            eq_query = eq_query.filter(Equipment.project_id == project_id)

        equipment_list = eq_query.limit(limit).all()

        logger.debug(f"[SEARCH] Found {len(equipment_list)} equipment of type {equipment_type}")

        for equipment in equipment_list:
            # Get locations for this equipment
            loc_query = db.query(EquipmentLocation).filter(
                EquipmentLocation.equipment_id == equipment.id
            ).join(Page).join(Document)
            if project_id is not None:
                loc_query = loc_query.filter(Document.project_id == project_id)
            locations = loc_query.limit(3).all()  # Limit locations per equipment

            if locations:
                for loc in locations:
                    page = loc.page
                    doc = page.document

                    doc_response = DocumentResponse(
                        id=doc.id,
                        filename=doc.filename,
                        original_filename=doc.original_filename,
                        title=doc.title,
                        drawing_number=doc.drawing_number,
                        revision=doc.revision,
                        system=doc.system,
                        area=doc.area,
                        file_size=doc.file_size,
                        page_count=doc.page_count,
                        upload_date=doc.upload_date,
                        processed=doc.processed
                    )

                    results.append(SearchResult(
                        equipment=EquipmentBrief(id=equipment.id, tag=equipment.tag, equipment_type=equipment.equipment_type),
                        document=doc_response,
                        page_number=page.page_number,
                        relevance_score=1.0,  # High relevance for direct equipment type match
                        snippet=loc.context_text or f"Equipment {equipment.tag} found on this page",
                        match_type="equipment_type_search"
                    ))
            else:
                # No PDF location, but equipment exists - create a placeholder result
                # Try to find in supplementary docs
                eq_data = db.query(EquipmentData).join(SupplementaryDocument).filter(
                    EquipmentData.equipment_tag.ilike(f'%{equipment.tag}%')
                )
                if project_id is not None:
                    eq_data = eq_data.filter(SupplementaryDocument.project_id == project_id)
                eq_data = eq_data.first()

                if eq_data:
                    doc = eq_data.document
                    doc_response = DocumentResponse(
                        id=doc.id,
                        filename=doc.filename,
                        original_filename=doc.original_filename,
                        title=doc.original_filename,
                        drawing_number=None,
                        revision=None,
                        system=None,
                        area=None,
                        file_size=doc.file_size,
                        page_count=1,
                        upload_date=doc.created_at,
                        processed=doc.processed
                    )

                    # Build snippet from data
                    try:
                        data = json.loads(eq_data.data_json)
                        snippet = f"{eq_data.data_type}: " + ", ".join(f"{k}={v}" for k, v in list(data.items())[:5])
                    except (json.JSONDecodeError, TypeError):
                        snippet = f"{equipment.tag} - {eq_data.data_type}"

                    results.append(SearchResult(
                        equipment=EquipmentBrief(id=equipment.id, tag=equipment.tag, equipment_type=equipment.equipment_type),
                        document=doc_response,
                        page_number=1,
                        relevance_score=0.95,
                        snippet=snippet,
                        match_type="equipment_type_search",
                        source_location=eq_data.source_location
                    ))

        return results

    def _find_aliases_in_query(self, db: Session, query: str, project_id: int = None) -> List[str]:
        """
        Search for equipment aliases mentioned in the query text.

        This catches cases where users type descriptions like:
        - "Air Handling Unit 1" -> matches alias -> returns "AHU-1"
        - "Supply Fan" -> matches alias -> returns "SF-1"
        """
        found_tags = []
        query_upper = query.upper()

        # Get all aliases (with their equipment tags)
        alias_query = db.query(EquipmentAlias, Equipment).join(
            Equipment, EquipmentAlias.equipment_id == Equipment.id
        )
        if project_id:
            alias_query = alias_query.filter(Equipment.project_id == project_id)

        # Check each alias against the query
        for alias, equipment in alias_query.all():
            alias_upper = alias.alias.upper()
            # Check if alias appears in query (as whole word/phrase)
            if len(alias_upper) >= 3:  # Only check aliases with 3+ chars to avoid false matches
                # Use word boundary matching for short aliases, substring for longer ones
                if len(alias_upper) <= 5:
                    # Short alias - need word boundary
                    pattern = r'\b' + re.escape(alias_upper) + r'\b'
                    if re.search(pattern, query_upper):
                        if equipment.tag not in found_tags:
                            found_tags.append(equipment.tag)
                            logger.debug(f"[SEARCH] Alias match: '{alias.alias}' -> {equipment.tag}")
                else:
                    # Longer alias - substring match is fine
                    if alias_upper in query_upper:
                        if equipment.tag not in found_tags:
                            found_tags.append(equipment.tag)
                            logger.debug(f"[SEARCH] Alias match: '{alias.alias}' -> {equipment.tag}")

        return found_tags

    def _calculate_relevance_score(
        self,
        base_score: float,
        match_type: str,
        query: str,
        query_type: QueryType,
        equipment_tags: List[str],
        result_equipment_tag: str = None,
        snippet: str = None,
        data_type: str = None
    ) -> float:
        """
        Calculate enhanced relevance score based on multiple factors.

        Factors:
        1. Base score from search method
        2. Match type boost (exact > text > semantic > keyword)
        3. Equipment tag match boost
        4. Query type alignment boost
        5. Snippet quality boost
        """
        score = base_score

        # 1. Match type multiplier
        match_type_multipliers = {
            "exact": 1.5,           # Exact equipment location match
            "text_search": 1.3,     # Found in OCR/AI analysis
            "semantic": 1.0,        # Vector similarity
            "keyword": 0.8,         # Basic keyword match
            "supplementary_semantic": 1.1,  # Supplementary docs are valuable
            "equipment_data": 1.4,  # Structured equipment data is high value
        }
        multiplier = match_type_multipliers.get(match_type, 1.0)
        score *= multiplier

        # 2. Equipment tag match boost - if result contains a queried equipment tag
        if result_equipment_tag and equipment_tags:
            tag_upper = result_equipment_tag.upper()
            if any(tag_upper == et.upper() for et in equipment_tags):
                score *= 1.3  # 30% boost for direct equipment match

        # 3. Query type alignment boost
        if data_type:
            # Boost when data type matches query intent
            query_type_data_alignment = {
                QueryType.EQUIPMENT_LOOKUP: ["SPECIFICATION", "SCHEDULE_ENTRY"],
                QueryType.RELATIONSHIP: ["SPECIFICATION"],
                QueryType.UPSTREAM_DOWNSTREAM: ["SPECIFICATION"],
                QueryType.WIRE_TRACE: ["IO_POINT"],
                QueryType.GENERAL: [],
            }
            aligned_types = query_type_data_alignment.get(query_type, [])
            if data_type in aligned_types:
                score *= 1.2  # 20% boost for aligned data type

        # 4. Query keyword boost - check if query keywords appear in snippet
        if snippet:
            query_words = set(query.lower().split())
            # Remove common words
            stop_words = {"what", "where", "is", "the", "a", "an", "and", "or", "for", "to", "of", "in", "on"}
            query_words -= stop_words

            snippet_lower = snippet.lower()
            matches = sum(1 for word in query_words if word in snippet_lower)
            if matches > 0:
                keyword_boost = min(1.0 + (matches * 0.1), 1.5)  # Up to 50% boost
                score *= keyword_boost

        # 5. Snippet quality - penalize very short snippets
        if snippet:
            if len(snippet) < 50:
                score *= 0.8  # Penalize very short snippets
            elif len(snippet) > 200:
                score *= 1.1  # Boost substantial snippets

        # Cap score at 2.0 to prevent runaway scores
        return min(score, 2.0)

    def search(self, db: Session, query: str, limit: int = 30, project_id: int = None, max_per_document: int = 5, rewrite_query: bool = True) -> SearchResponse:
        """Perform comprehensive hybrid search across ALL document types.

        Args:
            db: Database session
            query: Search query
            limit: Maximum results to return
            project_id: Optional project ID to scope search to
            max_per_document: Maximum results per document for diversity
            rewrite_query: Whether to use LLM to expand/improve the query (default True)
        """
        start_time = time.time()
        original_query = query

        # Step 0: Query rewriting with LLM for better search results
        if rewrite_query and self._has_llm():
            search_query, original_query = self.rewrite_query(query)
        else:
            search_query = query

        query_type = self.classify_query(original_query)  # Use original for classification
        all_results: List[SearchResult] = []
        existing_keys = set()
        document_counts: dict[int, int] = {}

        # Detect if this is a "list all [equipment type]" query
        detected_equipment_type = self._detect_equipment_type_query(original_query)

        # Track equipment tags we've already included (for equipment type search)
        included_equipment_tags = set()

        def add_result(result: SearchResult, skip_doc_limit: bool = False) -> bool:
            """Add result if not duplicate and within per-document limit

            Args:
                result: SearchResult to add
                skip_doc_limit: If True, bypass per-document limit (for equipment type search)
            """
            # Create unique key based on document + page/location
            if result.source_location:
                key = (result.document.id, result.source_location)
            else:
                key = (result.document.id, result.page_number)

            if key in existing_keys:
                return False

            # Check per-document limit (unless skipped)
            if not skip_doc_limit:
                doc_count = document_counts.get(result.document.id, 0)
                if doc_count >= max_per_document:
                    return False

            existing_keys.add(key)
            document_counts[result.document.id] = document_counts.get(result.document.id, 0) + 1
            all_results.append(result)
            return True

        # Extract equipment tags from BOTH original and rewritten queries
        equipment_in_original = extraction_service.extract_equipment_tags(original_query)
        equipment_in_rewritten = extraction_service.extract_equipment_tags(search_query)
        equipment_tags_raw = list(set(
            [eq.tag for eq in equipment_in_original] +
            [eq.tag for eq in equipment_in_rewritten]
        ))

        # Also search for aliases in both queries
        alias_matches = self._find_aliases_in_query(db, original_query, project_id)
        alias_matches += self._find_aliases_in_query(db, search_query, project_id)
        for tag in alias_matches:
            if tag not in equipment_tags_raw:
                equipment_tags_raw.append(tag)

        # Expand equipment tags with aliases for better matching
        if equipment_tags_raw:
            equipment_tags = self.expand_equipment_tags_with_aliases(db, equipment_tags_raw, project_id)
        else:
            equipment_tags = []

        print(f"\n[SEARCH] === Starting search ===")
        logger.debug(f"[SEARCH] Original query: {original_query[:60]}...")
        if search_query != original_query:
            logger.debug(f"[SEARCH] Rewritten query: {search_query[:80]}...")
        logger.debug(f"[SEARCH] Equipment tags found: {equipment_tags_raw}")
        if len(equipment_tags) > len(equipment_tags_raw):
            logger.debug(f"[SEARCH] Expanded with aliases: {equipment_tags}")
        if detected_equipment_type:
            logger.debug(f"[SEARCH] Detected equipment type query: {detected_equipment_type}")
        logger.debug(f"[SEARCH] Project ID: {project_id}")

        # === SEARCH ALL SOURCES (using rewritten query for semantic/keyword) ===

        # 0. Equipment type search (for "list all X" queries)
        if detected_equipment_type:
            type_results = self._search_equipment_by_type(db, detected_equipment_type, 50, project_id)
            logger.debug(f"[SEARCH] 0. Equipment type search ({detected_equipment_type}): {len(type_results)} results")
            # Add at least one result per unique equipment tag (skip doc limit for first)
            for r in type_results:
                eq_tag = r.equipment.tag if r.equipment else None
                if eq_tag and eq_tag not in included_equipment_tags:
                    # First result for this equipment tag - skip doc limit to ensure inclusion
                    if add_result(r, skip_doc_limit=True):
                        included_equipment_tags.add(eq_tag)
                else:
                    # Additional results for same tag - apply normal limits
                    add_result(r)
            # Also add all equipment of this type to equipment_tags for other searches
            for r in type_results:
                if r.equipment and r.equipment.tag not in equipment_tags:
                    equipment_tags.append(r.equipment.tag)

        # 1. Exact equipment match from PDF (highest relevance)
        if equipment_tags:
            exact_results = self._exact_equipment_search(db, equipment_tags, 20, project_id)
            logger.debug(f"[SEARCH] 1. Exact equipment match: {len(exact_results)} results")
            for r in exact_results:
                add_result(r)

        # 2. Text search for equipment tags in PDF
        if equipment_tags:
            text_results = self._text_search_for_equipment(db, equipment_tags, 20, project_id)
            logger.debug(f"[SEARCH] 2. Text search (PDF): {len(text_results)} results")
            for r in text_results:
                add_result(r)

        # 3. Semantic search in PDF (use rewritten query for better embeddings)
        semantic_results = self._semantic_search(db, search_query, 20, project_id)
        logger.debug(f"[SEARCH] 3. Semantic search (PDF): {len(semantic_results)} results")
        for r in semantic_results:
            add_result(r)

        # 4. Keyword search in PDF (use rewritten query for expanded terms)
        keyword_results = self._keyword_search(db, search_query, 20, project_id)
        logger.debug(f"[SEARCH] 4. Keyword search (PDF): {len(keyword_results)} results")
        for r in keyword_results:
            add_result(r)

        # 5. Supplementary chunks semantic search (use rewritten query)
        supp_chunk_results = self._search_supplementary_chunks(db, search_query, 15, project_id)
        logger.debug(f"[SEARCH] 5. Supplementary chunks: {len(supp_chunk_results)} results")
        for r in supp_chunk_results:
            add_result(r)

        # 6. Equipment data from supplementary docs (always run if equipment tags)
        if equipment_tags:
            eq_data_results = self._search_equipment_data(db, equipment_tags, None, 15, project_id)
            logger.debug(f"[SEARCH] 6. Equipment data: {len(eq_data_results)} results")
            for r in eq_data_results:
                add_result(r)

        # === ENHANCED RELEVANCE SCORING ===
        # Recalculate scores with multiple factors
        for result in all_results:
            # Extract data_type from metadata if available (for equipment_data results)
            data_type = None
            if result.match_type == "equipment_data" and result.snippet:
                # Try to extract data type from snippet (e.g., "SPECIFICATION: ..." or "IO_POINT: ...")
                for dt in ["SPECIFICATION", "IO_POINT", "ALARM", "SCHEDULE_ENTRY", "SEQUENCE"]:
                    if dt in result.snippet.upper():
                        data_type = dt
                        break

            enhanced_score = self._calculate_relevance_score(
                base_score=result.relevance_score,
                match_type=result.match_type,
                query=query,
                query_type=query_type,
                equipment_tags=equipment_tags,
                result_equipment_tag=result.equipment.tag if result.equipment else None,
                snippet=result.snippet,
                data_type=data_type
            )
            # Update the result's relevance score
            result.relevance_score = enhanced_score

        # Sort all results by enhanced relevance score
        all_results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Count result types for logging
        pdf_count = sum(1 for r in all_results if r.match_type in ["exact", "text_search", "semantic", "keyword"])
        supp_count = sum(1 for r in all_results if r.match_type in ["supplementary_semantic", "equipment_data"])

        logger.debug(f"[SEARCH] === Total: {len(all_results)} results ({pdf_count} PDF, {supp_count} supplementary) ===\n")

        response_time = int((time.time() - start_time) * 1000)

        return SearchResponse(
            query=query,
            query_type=query_type,
            results=all_results[:limit],
            total_count=len(all_results),
            response_time_ms=response_time
        )

    def _text_search_for_equipment(self, db: Session, tags: List[str], limit: int, project_id: int = None) -> List[SearchResult]:
        """Search for equipment mentions in OCR text and AI analysis"""
        results = []

        for tag in tags:
            # Search in OCR text, AI analysis, and AI equipment list
            query = db.query(Page).join(Document).filter(
                or_(
                    Page.ocr_text.ilike(f"%{tag}%"),
                    Page.ai_analysis.ilike(f"%{tag}%"),
                    Page.ai_equipment_list.ilike(f"%{tag}%")
                )
            )
            if project_id is not None:
                query = query.filter(Document.project_id == project_id)
            pages = query.limit(limit).all()

            for page in pages:
                doc = page.document
                doc_response = DocumentResponse(
                    id=doc.id,
                    filename=doc.filename,
                    original_filename=doc.original_filename,
                    title=doc.title,
                    drawing_number=doc.drawing_number,
                    revision=doc.revision,
                    system=doc.system,
                    area=doc.area,
                    file_size=doc.file_size,
                    page_count=doc.page_count,
                    upload_date=doc.upload_date,
                    processed=doc.processed
                )

                # Extract context around the tag mention
                snippet = self._extract_context(page.ocr_text or "", tag)
                if not snippet and page.ai_analysis:
                    snippet = self._extract_context(page.ai_analysis, tag)

                results.append(SearchResult(
                    equipment=EquipmentBrief(id=0, tag=tag, equipment_type="UNKNOWN"),
                    document=doc_response,
                    page_number=page.page_number,
                    relevance_score=0.9,
                    snippet=snippet or f"Equipment {tag} mentioned on this page",
                    match_type="text_search"
                ))

        return results

    def _extract_context(self, text: str, tag: str, context_chars: int = 150) -> str:
        """Extract text context around a tag mention"""
        if not text:
            return ""

        # Case-insensitive search
        text_lower = text.lower()
        tag_lower = tag.lower()

        pos = text_lower.find(tag_lower)
        if pos == -1:
            return ""

        start = max(0, pos - context_chars)
        end = min(len(text), pos + len(tag) + context_chars)

        context = text[start:end].strip()
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."

        return context

    def _exact_equipment_search(self, db: Session, tags: List[str], limit: int, project_id: int = None) -> List[SearchResult]:
        """Search for exact equipment tag matches"""
        results = []

        for tag in tags:
            eq_query = db.query(Equipment).filter(
                func.upper(Equipment.tag) == tag.upper()
            )
            if project_id is not None:
                eq_query = eq_query.filter(Equipment.project_id == project_id)
            equipment = eq_query.first()

            if equipment:
                loc_query = db.query(EquipmentLocation).filter(
                    EquipmentLocation.equipment_id == equipment.id
                ).join(Page).join(Document)
                if project_id is not None:
                    loc_query = loc_query.filter(Document.project_id == project_id)
                locations = loc_query.limit(limit).all()

                for loc in locations:
                    page = loc.page
                    doc = page.document

                    doc_response = DocumentResponse(
                        id=doc.id,
                        filename=doc.filename,
                        original_filename=doc.original_filename,
                        title=doc.title,
                        drawing_number=doc.drawing_number,
                        revision=doc.revision,
                        system=doc.system,
                        area=doc.area,
                        file_size=doc.file_size,
                        page_count=doc.page_count,
                        upload_date=doc.upload_date,
                        processed=doc.processed
                    )

                    results.append(SearchResult(
                        equipment=EquipmentBrief(id=equipment.id, tag=equipment.tag, equipment_type=equipment.equipment_type),
                        document=doc_response,
                        page_number=page.page_number,
                        relevance_score=1.0,
                        snippet=loc.context_text,
                        match_type="exact"
                    ))

        return results

    def _semantic_search(self, db: Session, query: str, limit: int, project_id: int = None) -> List[SearchResult]:
        """Search using vector similarity"""
        query_embedding = embedding_service.generate_embedding(query)

        # Build SQL with optional project filter
        project_filter = "AND d.project_id = :project_id" if project_id is not None else ""

        sql = text(f"""
            SELECT
                p.id,
                p.document_id,
                p.page_number,
                p.ocr_text,
                p.ai_analysis,
                p.ai_equipment_list,
                d.filename,
                d.original_filename,
                d.title,
                d.drawing_number,
                d.revision,
                d.system,
                d.area,
                d.file_size,
                d.page_count,
                d.upload_date,
                d.processed,
                1 - (p.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM pages p
            JOIN documents d ON p.document_id = d.id
            WHERE p.embedding IS NOT NULL {project_filter}
            ORDER BY p.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        params = {"embedding": str(query_embedding), "limit": limit}
        if project_id is not None:
            params["project_id"] = project_id
        result = db.execute(sql, params)

        results = []
        for row in result:
            doc_response = DocumentResponse(
                id=row.document_id,
                filename=row.filename,
                original_filename=row.original_filename,
                title=row.title,
                drawing_number=row.drawing_number,
                revision=row.revision,
                system=row.system,
                area=row.area,
                file_size=row.file_size,
                page_count=row.page_count,
                upload_date=row.upload_date,
                processed=row.processed
            )

            # Prefer AI analysis for snippet if available
            snippet_source = row.ocr_text
            if hasattr(row, 'ai_analysis') and row.ai_analysis:
                snippet_source = f"{row.ai_analysis}\n\n{row.ocr_text}"
            snippet = snippet_source[:200] + "..." if snippet_source and len(snippet_source) > 200 else snippet_source

            results.append(SearchResult(
                equipment=None,
                document=doc_response,
                page_number=row.page_number,
                relevance_score=float(row.similarity),
                snippet=snippet,
                match_type="semantic"
            ))

        return results

    def _keyword_search(self, db: Session, query: str, limit: int, project_id: int = None) -> List[SearchResult]:
        """Full-text keyword search including AI analysis"""
        search_term = f"%{query}%"

        kw_query = db.query(Page).join(Document).filter(
            or_(
                Page.ocr_text.ilike(search_term),
                Page.ai_analysis.ilike(search_term),
                Page.ai_equipment_list.ilike(search_term),
                Document.title.ilike(search_term),
                Document.drawing_number.ilike(search_term)
            )
        )
        if project_id is not None:
            kw_query = kw_query.filter(Document.project_id == project_id)
        pages = kw_query.limit(limit).all()

        results = []
        for page in pages:
            doc = page.document
            doc_response = DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                title=doc.title,
                drawing_number=doc.drawing_number,
                revision=doc.revision,
                system=doc.system,
                area=doc.area,
                file_size=doc.file_size,
                page_count=doc.page_count,
                upload_date=doc.upload_date,
                processed=doc.processed
            )

            snippet = page.ocr_text[:200] + "..." if page.ocr_text and len(page.ocr_text) > 200 else page.ocr_text

            results.append(SearchResult(
                equipment=None,
                document=doc_response,
                page_number=page.page_number,
                relevance_score=0.5,
                snippet=snippet,
                match_type="keyword"
            ))

        return results

    def get_equipment_relationships(self, db: Session, equipment_tag: str, direction: str = "both") -> dict:
        """Get equipment relationships (controls/controlled_by)"""
        equipment = db.query(Equipment).filter(
            func.upper(Equipment.tag) == equipment_tag.upper()
        ).first()

        if not equipment:
            return {"error": f"Equipment {equipment_tag} not found"}

        result = {
            "equipment": equipment.tag,
            "controls": [],
            "controlled_by": [],
            "powers": [],
            "powered_by": []
        }

        if direction in ["both", "outgoing"]:
            outgoing = db.query(EquipmentRelationship).filter(
                EquipmentRelationship.source_id == equipment.id
            ).all()

            for rel in outgoing:
                target = db.query(Equipment).filter(Equipment.id == rel.target_id).first()
                if target:
                    if rel.relationship_type == "CONTROLS":
                        result["controls"].append(target.tag)
                    elif rel.relationship_type == "POWERS":
                        result["powers"].append(target.tag)

        if direction in ["both", "incoming"]:
            incoming = db.query(EquipmentRelationship).filter(
                EquipmentRelationship.target_id == equipment.id
            ).all()

            for rel in incoming:
                source = db.query(Equipment).filter(Equipment.id == rel.source_id).first()
                if source:
                    if rel.relationship_type == "CONTROLS":
                        result["controlled_by"].append(source.tag)
                    elif rel.relationship_type == "POWERS":
                        result["powered_by"].append(source.tag)

        return result

    def get_upstream_equipment(self, db: Session, equipment_tag: str, depth: int = 3) -> List[str]:
        """Get upstream equipment chain"""
        visited = set()
        upstream = []

        def traverse(tag: str, current_depth: int):
            if current_depth > depth or tag in visited:
                return
            visited.add(tag)

            equipment = db.query(Equipment).filter(
                func.upper(Equipment.tag) == tag.upper()
            ).first()

            if not equipment:
                return

            incoming = db.query(EquipmentRelationship).filter(
                EquipmentRelationship.target_id == equipment.id,
                EquipmentRelationship.relationship_type.in_(["POWERS", "FEEDS"])
            ).all()

            for rel in incoming:
                source = db.query(Equipment).filter(Equipment.id == rel.source_id).first()
                if source and source.tag not in visited:
                    upstream.append(source.tag)
                    traverse(source.tag, current_depth + 1)

        traverse(equipment_tag, 0)
        return upstream

    def _search_supplementary_chunks(self, db: Session, query: str, limit: int, project_id: int = None) -> List[SearchResult]:
        """Search supplementary document chunks using vector similarity"""
        query_embedding = embedding_service.generate_embedding(query)

        # Build SQL with optional project filter
        project_filter = ""
        if project_id is not None:
            project_filter = "AND sd.project_id = :project_id"

        sql = text(f"""
            SELECT
                sc.id,
                sc.document_id,
                sc.chunk_index,
                sc.content,
                sc.source_location,
                sc.equipment_tags,
                sd.filename,
                sd.original_filename,
                sd.document_type,
                sd.project_id,
                sd.created_at,
                1 - (sc.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM supplementary_chunks sc
            JOIN supplementary_documents sd ON sc.document_id = sd.id
            WHERE sc.embedding IS NOT NULL {project_filter}
            ORDER BY sc.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        params = {"embedding": str(query_embedding), "limit": limit}
        if project_id is not None:
            params["project_id"] = project_id
        result = db.execute(sql, params)

        results = []
        for row in result:
            # Create a pseudo-document response for supplementary docs
            doc_response = DocumentResponse(
                id=row.document_id,
                filename=row.filename,
                original_filename=row.original_filename,
                title=row.original_filename,  # Use filename as title
                drawing_number=None,
                revision=None,
                system=None,
                area=None,
                file_size=None,
                page_count=1,
                upload_date=row.created_at or datetime.utcnow(),
                processed=2
            )

            # Parse equipment tags if present
            equipment_brief = None
            if row.equipment_tags:
                try:
                    tags = json.loads(row.equipment_tags)
                    if tags:
                        equipment_brief = EquipmentBrief(id=0, tag=tags[0], equipment_type="UNKNOWN")
                except (json.JSONDecodeError, TypeError, IndexError) as e:
                    logger.debug(f"Failed to parse equipment tags: {e}")

            results.append(SearchResult(
                equipment=equipment_brief,
                document=doc_response,
                page_number=row.chunk_index + 1,  # Use chunk index as page
                relevance_score=float(row.similarity),
                snippet=row.content[:300] + "..." if len(row.content) > 300 else row.content,
                match_type="supplementary_semantic",
                source_location=row.source_location
            ))

        return results

    def _search_equipment_data(self, db: Session, tags: List[str], data_types: List[str] = None,
                               limit: int = 10, project_id: int = None) -> List[SearchResult]:
        """Search structured equipment data by tags and optional data types"""
        results = []

        for tag in tags:
            query = db.query(EquipmentData).join(SupplementaryDocument).filter(
                EquipmentData.equipment_tag.ilike(f"%{tag}%")
            )
            if project_id is not None:
                query = query.filter(SupplementaryDocument.project_id == project_id)
            if data_types:
                query = query.filter(EquipmentData.data_type.in_(data_types))

            data_entries = query.limit(limit).all()

            for entry in data_entries:
                doc = entry.document
                doc_response = DocumentResponse(
                    id=doc.id,
                    filename=doc.filename,
                    original_filename=doc.original_filename,
                    title=doc.original_filename,
                    drawing_number=None,
                    revision=None,
                    system=None,
                    area=None,
                    file_size=doc.file_size,
                    page_count=1,
                    upload_date=doc.created_at,
                    processed=doc.processed
                )

                # Build snippet from data_json
                try:
                    data = json.loads(entry.data_json)
                    snippet = f"{entry.data_type}: " + ", ".join(f"{k}={v}" for k, v in list(data.items())[:5])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.debug(f"Failed to parse equipment data JSON: {e}")
                    snippet = f"{entry.data_type} data for {entry.equipment_tag}"

                results.append(SearchResult(
                    equipment=EquipmentBrief(id=entry.equipment_id or 0, tag=entry.equipment_tag, equipment_type="UNKNOWN"),
                    document=doc_response,
                    page_number=1,
                    relevance_score=entry.match_confidence or 0.9,
                    snippet=snippet,
                    match_type="equipment_data",
                    source_location=entry.source_location
                ))

        return results


search_service = SearchService()
