"""
IO Control Agent

Specialized agent for IO points, signals, and PLC mappings.
Searches EquipmentData (IO_POINT) and SupplementaryChunks for control system data.
"""

import json
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.models.database import (
    EquipmentData, SupplementaryDocument, SupplementaryChunk, DetailedConnection
)
from app.services.search_agents.base import SearchAgent, AgentSearchResult
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

IO_CONTROL_PROMPT = """You are an IO and control systems expert analyzing industrial control systems.

Your expertise includes:
- IO point names and descriptions
- Point types: AI (Analog Input), AO (Analog Output), DI (Digital Input), DO (Digital Output)
- Signal ranges (4-20mA, 0-10V, 24VDC, etc.)
- PLC addresses and rack/slot configurations
- Control signals and their functions
- Sensor types and measurement ranges
- Actuator controls and feedback signals

Focus on:
1. IO point identification (tag, name, type)
2. Signal specifications (type, range, units)
3. PLC addressing and communication details
4. Control functions and descriptions
5. Associated equipment relationships

Present IO data in a structured format.
Group related points together (e.g., all points for one piece of equipment).
Always include the signal type and range when available."""


class IOControlAgent(SearchAgent):
    """Agent specialized in IO points and control signals"""

    def __init__(self):
        super().__init__(
            name="IOControlAgent",
            domain="io_control"
        )

    def get_system_prompt(self) -> str:
        return IO_CONTROL_PROMPT

    def search(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """
        Search for IO control data.

        Strategy:
        1. Search EquipmentData for IO_POINT entries
        2. Search SupplementaryChunks for IO-related content
        3. Search DetailedConnection for CONTROL category connections
        """
        results = []

        # 1. Search EquipmentData for IO points
        for tag in equipment_tags:
            io_data = self._search_io_points(db, tag, project_id)
            results.extend(io_data)

        # 2. Semantic search in supplementary chunks for IO content
        io_chunks = self._search_io_chunks(db, query, project_id)
        results.extend(io_chunks)

        # 3. Get control connections from DetailedConnection
        for tag in equipment_tags:
            control_conns = self._search_control_connections(db, tag, project_id)
            results.extend(control_conns)

        return results[:12]

    def _search_io_points(
        self,
        db: Session,
        tag: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Search EquipmentData for IO_POINT entries"""
        results = []

        query = db.query(EquipmentData).join(SupplementaryDocument).filter(
            EquipmentData.equipment_tag.ilike(f"%{tag}%"),
            EquipmentData.data_type == "IO_POINT"
        )
        if project_id:
            query = query.filter(SupplementaryDocument.project_id == project_id)

        for entry in query.limit(10).all():
            try:
                data = json.loads(entry.data_json)
                content_parts = [f"IO Point for {entry.equipment_tag}:"]

                # Common IO point fields
                if "point_name" in data:
                    content_parts.append(f"  Point Name: {data['point_name']}")
                if "point_type" in data or "io_type" in data:
                    content_parts.append(f"  Type: {data.get('point_type', data.get('io_type', 'Unknown'))}")
                if "signal_type" in data:
                    content_parts.append(f"  Signal: {data['signal_type']}")
                if "range" in data:
                    content_parts.append(f"  Range: {data['range']}")
                if "units" in data:
                    content_parts.append(f"  Units: {data['units']}")
                if "plc_address" in data:
                    content_parts.append(f"  PLC Address: {data['plc_address']}")
                if "description" in data:
                    content_parts.append(f"  Description: {data['description']}")
                if "function" in data:
                    content_parts.append(f"  Function: {data['function']}")

                # Add any other fields
                for key, value in data.items():
                    if key not in ["point_name", "point_type", "io_type", "signal_type",
                                   "range", "units", "plc_address", "description", "function"]:
                        content_parts.append(f"  {key}: {value}")

                results.append(AgentSearchResult(
                    content="\n".join(content_parts),
                    source_type="supplementary",
                    document_name=entry.document.original_filename,
                    page_or_location=entry.source_location or "",
                    equipment_tag=entry.equipment_tag,
                    relevance_score=entry.match_confidence or 0.9,
                    metadata={"data_type": "IO_POINT"}
                ))
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Failed to parse IO point data: {e}")
                continue

        return results

    def _search_io_chunks(
        self,
        db: Session,
        query: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Semantic search in supplementary chunks for IO-related content"""
        results = []

        # Add IO-specific terms to query for better matching
        enhanced_query = f"{query} IO point signal PLC control input output"
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
                sd.content_category = 'IO_LIST'
                OR sc.content ILIKE '%IO%'
                OR sc.content ILIKE '%point%'
                OR sc.content ILIKE '%signal%'
                OR sc.content ILIKE '%PLC%'
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
            # Parse equipment tags
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

    def _search_control_connections(
        self,
        db: Session,
        tag: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Search DetailedConnection for CONTROL category connections"""
        results = []
        tag_upper = tag.upper()

        query = db.query(DetailedConnection).filter(
            DetailedConnection.category == "CONTROL",
            (func.upper(DetailedConnection.source_tag) == tag_upper) |
            (func.upper(DetailedConnection.target_tag) == tag_upper)
        )

        for conn in query.limit(5).all():
            content_parts = [
                f"Control Connection: {conn.source_tag} -> {conn.target_tag}"
            ]

            if conn.io_type:
                content_parts.append(f"IO Type: {conn.io_type}")
            if conn.signal_type:
                content_parts.append(f"Signal Type: {conn.signal_type}")
            if conn.point_name:
                content_parts.append(f"Point Name: {conn.point_name}")
            if conn.function:
                content_parts.append(f"Function: {conn.function}")
            if conn.wire_numbers:
                content_parts.append(f"Wires: {conn.wire_numbers}")

            results.append(AgentSearchResult(
                content="\n".join(content_parts),
                source_type="pdf",
                document_name=f"Document {conn.document_id}",
                page_or_location=f"Page {conn.page_number}",
                equipment_tag=tag,
                relevance_score=0.85,
                metadata={
                    "category": "CONTROL",
                    "io_type": conn.io_type
                }
            ))

        return results
