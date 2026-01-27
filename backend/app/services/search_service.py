import re
import time
import logging
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func

from app.models.database import Document, Page, Equipment, EquipmentLocation, EquipmentRelationship, SupplementaryChunk, EquipmentData, SupplementaryDocument
from app.models.schemas import QueryType, SearchResult, SearchResponse, DocumentResponse, EquipmentBrief
from app.services.embedding_service import embedding_service
from app.services.extraction_service import extraction_service

logger = logging.getLogger(__name__)


class SearchService:
    """Hybrid search: exact match + semantic + keyword"""

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

    def search(self, db: Session, query: str, limit: int = 10, project_id: int = None, max_per_document: int = 3) -> SearchResponse:
        """Perform hybrid search with comprehensive equipment detection

        Args:
            db: Database session
            query: Search query
            limit: Maximum results to return
            project_id: Optional project ID to scope search to
            max_per_document: Maximum results per document (ensures cross-document diversity)
        """
        start_time = time.time()

        query_type = self.classify_query(query)
        results: List[SearchResult] = []
        existing_pages = set()
        document_counts: dict[int, int] = {}  # Track results per document

        def can_add_result(doc_id: int) -> bool:
            """Check if we can add another result from this document"""
            return document_counts.get(doc_id, 0) < max_per_document

        def add_result(result: SearchResult) -> bool:
            """Add result if not duplicate and within per-document limit"""
            key = (result.document.id, result.page_number)
            if key in existing_pages:
                return False
            if not can_add_result(result.document.id):
                return False
            existing_pages.add(key)
            document_counts[result.document.id] = document_counts.get(result.document.id, 0) + 1
            results.append(result)
            return True

        equipment_in_query = extraction_service.extract_equipment_tags(query)
        equipment_tags = [eq.tag for eq in equipment_in_query]

        # 1. Exact equipment match from equipment_locations table
        if equipment_tags:
            exact_results = self._exact_equipment_search(db, equipment_tags, limit * 3, project_id)  # Fetch more to allow filtering
            for r in exact_results:
                if len(results) >= limit:
                    break
                add_result(r)

        # 2. Text search for equipment tags in OCR text and AI analysis
        if equipment_tags and len(results) < limit:
            text_results = self._text_search_for_equipment(db, equipment_tags, limit * 3, project_id)
            for r in text_results:
                if len(results) >= limit:
                    break
                add_result(r)

        # 3. Semantic search
        if len(results) < limit:
            semantic_results = self._semantic_search(db, query, limit * 3, project_id)
            for r in semantic_results:
                if len(results) >= limit:
                    break
                add_result(r)

        # 4. Keyword search as fallback
        if len(results) < limit:
            keyword_results = self._keyword_search(db, query, limit * 3, project_id)
            for kr in keyword_results:
                if len(results) >= limit:
                    break
                add_result(kr)

        # 5. Search supplementary chunks (semantic)
        if len(results) < limit:
            supp_results = self._search_supplementary_chunks(db, query, limit * 2, project_id)
            for r in supp_results:
                if len(results) >= limit:
                    break
                # Check for duplicates by content similarity (simple check)
                is_duplicate = any(
                    r.snippet[:100] == existing.snippet[:100]
                    for existing in results if existing.snippet
                )
                if not is_duplicate:
                    results.append(r)

        # 6. Search equipment data for specific equipment queries
        if equipment_tags and len(results) < limit:
            eq_data_results = self._search_equipment_data(db, equipment_tags, None, limit, project_id)
            for r in eq_data_results:
                if len(results) >= limit:
                    break
                add_result(r)

        response_time = int((time.time() - start_time) * 1000)

        return SearchResponse(
            query=query,
            query_type=query_type,
            results=results[:limit],
            total_count=len(results),
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
        import json
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
                upload_date=None,
                processed=2
            )

            # Parse equipment tags if present
            equipment_brief = None
            if row.equipment_tags:
                try:
                    tags = json.loads(row.equipment_tags)
                    if tags:
                        equipment_brief = EquipmentBrief(id=0, tag=tags[0], equipment_type="UNKNOWN")
                except:
                    pass

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
        import json
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
                except:
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
