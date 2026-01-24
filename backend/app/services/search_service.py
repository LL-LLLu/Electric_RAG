import re
import time
import logging
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func

from app.models.database import Document, Page, Equipment, EquipmentLocation, EquipmentRelationship
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

    def search(self, db: Session, query: str, limit: int = 10) -> SearchResponse:
        """Perform hybrid search"""
        start_time = time.time()

        query_type = self.classify_query(query)
        results: List[SearchResult] = []

        equipment_in_query = extraction_service.extract_equipment_tags(query)
        equipment_tags = [eq.tag for eq in equipment_in_query]

        # 1. Exact equipment match
        if equipment_tags:
            exact_results = self._exact_equipment_search(db, equipment_tags, limit)
            results.extend(exact_results)

        # 2. Semantic search
        if len(results) < limit:
            semantic_results = self._semantic_search(db, query, limit - len(results))
            results.extend(semantic_results)

        # 3. Keyword search as fallback
        if len(results) < limit:
            keyword_results = self._keyword_search(db, query, limit - len(results))
            existing_pages = {(r.document.id, r.page_number) for r in results}
            for kr in keyword_results:
                if (kr.document.id, kr.page_number) not in existing_pages:
                    results.append(kr)

        response_time = int((time.time() - start_time) * 1000)

        return SearchResponse(
            query=query,
            query_type=query_type,
            results=results[:limit],
            total_count=len(results),
            response_time_ms=response_time
        )

    def _exact_equipment_search(self, db: Session, tags: List[str], limit: int) -> List[SearchResult]:
        """Search for exact equipment tag matches"""
        results = []

        for tag in tags:
            equipment = db.query(Equipment).filter(
                func.upper(Equipment.tag) == tag.upper()
            ).first()

            if equipment:
                locations = db.query(EquipmentLocation).filter(
                    EquipmentLocation.equipment_id == equipment.id
                ).join(Page).join(Document).limit(limit).all()

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

    def _semantic_search(self, db: Session, query: str, limit: int) -> List[SearchResult]:
        """Search using vector similarity"""
        query_embedding = embedding_service.generate_embedding(query)

        sql = text("""
            SELECT
                p.id,
                p.document_id,
                p.page_number,
                p.ocr_text,
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
                1 - (p.embedding <=> :embedding::vector) as similarity
            FROM pages p
            JOIN documents d ON p.document_id = d.id
            WHERE p.embedding IS NOT NULL
            ORDER BY p.embedding <=> :embedding::vector
            LIMIT :limit
        """)

        result = db.execute(sql, {"embedding": str(query_embedding), "limit": limit})

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

            snippet = row.ocr_text[:200] + "..." if row.ocr_text and len(row.ocr_text) > 200 else row.ocr_text

            results.append(SearchResult(
                equipment=None,
                document=doc_response,
                page_number=row.page_number,
                relevance_score=float(row.similarity),
                snippet=snippet,
                match_type="semantic"
            ))

        return results

    def _keyword_search(self, db: Session, query: str, limit: int) -> List[SearchResult]:
        """Full-text keyword search"""
        search_term = f"%{query}%"

        pages = db.query(Page).join(Document).filter(
            or_(
                Page.ocr_text.ilike(search_term),
                Document.title.ilike(search_term),
                Document.drawing_number.ilike(search_term)
            )
        ).limit(limit).all()

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


search_service = SearchService()
