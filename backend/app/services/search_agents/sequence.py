"""
Sequence Agent

Specialized agent for operating sequences, modes, and control logic.
Searches SupplementaryChunks (SEQUENCE_OF_OPERATION content category).
"""

import json
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.database import SupplementaryDocument, SupplementaryChunk, EquipmentData
from app.services.search_agents.base import SearchAgent, AgentSearchResult
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

SEQUENCE_PROMPT = """You are a sequence of operations expert analyzing industrial process control and automation.

Your expertise includes:
- Operating sequences and procedures
- Start/stop sequences for equipment
- Operating modes (manual, auto, off)
- Mode transitions and conditions
- Control logic and decision points
- Process interlocks within sequences
- State machine logic
- Timing and delay requirements

Focus on:
1. Step-by-step sequence descriptions
2. Conditions for mode transitions
3. Start/stop sequence requirements
4. Control logic flow
5. Timing requirements and delays
6. Prerequisites and permissives for operations

Present sequences in clear, ordered steps.
Include timing requirements when specified.
Note any conditions or prerequisites for each step.
Highlight safety-related sequence steps."""


class SequenceAgent(SearchAgent):
    """Agent specialized in operating sequences and control logic"""

    def __init__(self):
        super().__init__(
            name="SequenceAgent",
            domain="sequence_operations"
        )

    def get_system_prompt(self) -> str:
        return SEQUENCE_PROMPT

    def search(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """
        Search for sequence of operation data.

        Strategy:
        1. Search SupplementaryChunks from SEQUENCE_OF_OPERATION documents
        2. Search EquipmentData for SEQUENCE type entries
        3. Semantic search for sequence-related content
        """
        results = []

        # 1. Search SEQUENCE_OF_OPERATION documents
        soo_results = self._search_sequence_documents(db, query, equipment_tags, project_id)
        results.extend(soo_results)

        # 2. Search EquipmentData for SEQUENCE entries
        for tag in equipment_tags:
            seq_data = self._search_sequence_data(db, tag, project_id)
            results.extend(seq_data)

        # 3. Semantic search for sequence content
        semantic_results = self._semantic_sequence_search(db, query, project_id)
        results.extend(semantic_results)

        return results[:12]

    def _search_sequence_documents(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Search chunks from SEQUENCE_OF_OPERATION documents"""
        results = []

        # Get sequence documents
        doc_query = db.query(SupplementaryDocument).filter(
            SupplementaryDocument.content_category == "SEQUENCE_OF_OPERATION"
        )
        if project_id:
            doc_query = doc_query.filter(SupplementaryDocument.project_id == project_id)

        seq_docs = doc_query.all()

        for doc in seq_docs:
            # Search chunks from this document
            chunk_query = db.query(SupplementaryChunk).filter(
                SupplementaryChunk.document_id == doc.id
            )

            # Filter by equipment tags if provided
            if equipment_tags:
                tag_filters = []
                for tag in equipment_tags:
                    tag_filters.append(SupplementaryChunk.content.ilike(f"%{tag}%"))
                    tag_filters.append(SupplementaryChunk.equipment_tags.ilike(f"%{tag}%"))

                from sqlalchemy import or_
                chunk_query = chunk_query.filter(or_(*tag_filters))

            chunks = chunk_query.limit(5).all()

            for chunk in chunks:
                equipment_tag = None
                if chunk.equipment_tags:
                    try:
                        tags = json.loads(chunk.equipment_tags)
                        if tags:
                            equipment_tag = tags[0]
                    except (json.JSONDecodeError, TypeError):
                        pass

                results.append(AgentSearchResult(
                    content=chunk.content[:600] if len(chunk.content) > 600 else chunk.content,
                    source_type="supplementary",
                    document_name=doc.original_filename,
                    page_or_location=chunk.source_location or f"Section {chunk.chunk_index + 1}",
                    equipment_tag=equipment_tag,
                    relevance_score=0.95,
                    metadata={"content_category": "SEQUENCE_OF_OPERATION"}
                ))

        return results

    def _search_sequence_data(
        self,
        db: Session,
        tag: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Search EquipmentData for SEQUENCE entries"""
        results = []

        query = db.query(EquipmentData).join(SupplementaryDocument).filter(
            EquipmentData.equipment_tag.ilike(f"%{tag}%"),
            EquipmentData.data_type == "SEQUENCE"
        )
        if project_id:
            query = query.filter(SupplementaryDocument.project_id == project_id)

        for entry in query.limit(5).all():
            try:
                data = json.loads(entry.data_json)
                content_parts = [f"Sequence for {entry.equipment_tag}:"]

                # Common sequence fields
                if "mode" in data:
                    content_parts.append(f"  Mode: {data['mode']}")
                if "sequence_name" in data:
                    content_parts.append(f"  Sequence: {data['sequence_name']}")
                if "steps" in data:
                    content_parts.append("  Steps:")
                    if isinstance(data["steps"], list):
                        for i, step in enumerate(data["steps"], 1):
                            if isinstance(step, dict):
                                step_desc = step.get("description", step.get("action", str(step)))
                            else:
                                step_desc = str(step)
                            content_parts.append(f"    {i}. {step_desc}")
                    else:
                        content_parts.append(f"    {data['steps']}")
                if "conditions" in data:
                    content_parts.append(f"  Conditions: {data['conditions']}")
                if "timing" in data:
                    content_parts.append(f"  Timing: {data['timing']}")
                if "description" in data:
                    content_parts.append(f"  Description: {data['description']}")

                results.append(AgentSearchResult(
                    content="\n".join(content_parts),
                    source_type="supplementary",
                    document_name=entry.document.original_filename,
                    page_or_location=entry.source_location or "",
                    equipment_tag=entry.equipment_tag,
                    relevance_score=entry.match_confidence or 0.9,
                    metadata={"data_type": "SEQUENCE"}
                ))
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Failed to parse sequence data: {e}")
                continue

        return results

    def _semantic_sequence_search(
        self,
        db: Session,
        query: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Semantic search for sequence-related content"""
        results = []

        # Enhance query with sequence-related terms
        enhanced_query = f"{query} sequence operation start stop mode control logic step procedure"
        query_embedding = embedding_service.generate_embedding(enhanced_query)

        project_filter = ""
        if project_id:
            project_filter = "AND sd.project_id = :project_id"

        sql = text(f"""
            SELECT
                sc.id,
                sc.document_id,
                sc.content,
                sc.source_location,
                sc.equipment_tags,
                sd.original_filename,
                sd.content_category,
                1 - (sc.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM supplementary_chunks sc
            JOIN supplementary_documents sd ON sc.document_id = sd.id
            WHERE sc.embedding IS NOT NULL
            AND (
                sd.content_category = 'SEQUENCE_OF_OPERATION'
                OR sc.content ILIKE '%sequence%'
                OR sc.content ILIKE '%start%'
                OR sc.content ILIKE '%stop%'
                OR sc.content ILIKE '%mode%'
                OR sc.content ILIKE '%operation%'
            )
            {project_filter}
            ORDER BY sc.embedding <=> CAST(:embedding AS vector)
            LIMIT 5
        """)

        params = {"embedding": str(query_embedding)}
        if project_id:
            params["project_id"] = project_id

        result = db.execute(sql, params)

        for row in result:
            equipment_tag = None
            if row.equipment_tags:
                try:
                    tags = json.loads(row.equipment_tags)
                    if tags:
                        equipment_tag = tags[0]
                except (json.JSONDecodeError, TypeError):
                    pass

            results.append(AgentSearchResult(
                content=row.content[:500] if len(row.content) > 500 else row.content,
                source_type="supplementary",
                document_name=row.original_filename,
                page_or_location=row.source_location or "",
                equipment_tag=equipment_tag,
                relevance_score=float(row.similarity),
                metadata={"content_category": row.content_category}
            ))

        return results
