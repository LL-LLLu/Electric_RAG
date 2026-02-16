"""
Alarm Interlock Agent

Specialized agent for alarms, interlocks, safety trips, and permissives.
Searches EquipmentData (ALARM) and DetailedConnection (INTERLOCK category).
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

ALARM_INTERLOCK_PROMPT = """You are an alarm and safety systems expert analyzing industrial safety and protection systems.

Your expertise includes:
- Alarm names, types, and setpoints
- Alarm categories (critical, warning, info)
- Interlock conditions and logic
- Safety trips and their triggers
- Permissives and enable conditions
- Protection coordination
- Emergency shutdown systems

Focus on:
1. Alarm identification (name, type, setpoint)
2. Alarm categories and priorities
3. Interlock logic and conditions
4. Safety trip causes and effects
5. Permissive conditions for equipment operation

Present safety information clearly with emphasis on:
- What triggers the alarm/trip
- What happens when triggered
- What conditions must be met (permissives)
- Priority and criticality level

Safety data should be presented precisely - setpoints must be exact values when available."""


class AlarmInterlockAgent(SearchAgent):
    """Agent specialized in alarms, interlocks, and safety systems"""

    def __init__(self):
        super().__init__(
            name="AlarmInterlockAgent",
            domain="alarm_interlock"
        )

    def get_system_prompt(self) -> str:
        return ALARM_INTERLOCK_PROMPT

    def search(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """
        Search for alarm and interlock data.

        Strategy:
        1. Search EquipmentData for ALARM entries
        2. Search DetailedConnection for INTERLOCK category
        3. Semantic search in supplementary chunks for alarm/safety content
        """
        results = []

        # 1. Search EquipmentData for alarms
        for tag in equipment_tags:
            alarm_data = self._search_alarm_data(db, tag, project_id)
            results.extend(alarm_data)

        # 2. Search DetailedConnection for interlocks
        for tag in equipment_tags:
            interlocks = self._search_interlocks(db, tag, project_id)
            results.extend(interlocks)

        # 3. Semantic search for alarm/safety content
        safety_chunks = self._search_safety_chunks(db, query, project_id)
        results.extend(safety_chunks)

        return results[:12]

    def _search_alarm_data(
        self,
        db: Session,
        tag: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Search EquipmentData for ALARM entries"""
        results = []

        query = db.query(EquipmentData).join(SupplementaryDocument).filter(
            EquipmentData.equipment_tag.ilike(f"%{tag}%"),
            EquipmentData.data_type == "ALARM"
        )
        if project_id:
            query = query.filter(SupplementaryDocument.project_id == project_id)

        for entry in query.limit(10).all():
            try:
                data = json.loads(entry.data_json)
                content_parts = [f"Alarm for {entry.equipment_tag}:"]

                # Common alarm fields
                if "alarm_name" in data:
                    content_parts.append(f"  Alarm Name: {data['alarm_name']}")
                if "alarm_type" in data:
                    content_parts.append(f"  Type: {data['alarm_type']}")
                if "setpoint" in data:
                    content_parts.append(f"  Setpoint: {data['setpoint']}")
                if "setpoint_high" in data:
                    content_parts.append(f"  High Setpoint: {data['setpoint_high']}")
                if "setpoint_low" in data:
                    content_parts.append(f"  Low Setpoint: {data['setpoint_low']}")
                if "category" in data or "priority" in data:
                    content_parts.append(f"  Priority: {data.get('category', data.get('priority', 'Unknown'))}")
                if "description" in data:
                    content_parts.append(f"  Description: {data['description']}")
                if "action" in data:
                    content_parts.append(f"  Action: {data['action']}")
                if "delay" in data:
                    content_parts.append(f"  Delay: {data['delay']}")

                # Add other fields
                for key, value in data.items():
                    if key not in ["alarm_name", "alarm_type", "setpoint", "setpoint_high",
                                   "setpoint_low", "category", "priority", "description",
                                   "action", "delay"]:
                        content_parts.append(f"  {key}: {value}")

                results.append(AgentSearchResult(
                    content="\n".join(content_parts),
                    source_type="supplementary",
                    document_name=entry.document.original_filename,
                    page_or_location=entry.source_location or "",
                    equipment_tag=entry.equipment_tag,
                    relevance_score=entry.match_confidence or 0.9,
                    metadata={"data_type": "ALARM"}
                ))
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Failed to parse alarm data: {e}")
                continue

        return results

    def _search_interlocks(
        self,
        db: Session,
        tag: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Search DetailedConnection for INTERLOCK category"""
        results = []
        tag_upper = tag.upper()

        query = db.query(DetailedConnection).filter(
            DetailedConnection.category == "INTERLOCK",
            (func.upper(DetailedConnection.source_tag) == tag_upper) |
            (func.upper(DetailedConnection.target_tag) == tag_upper)
        )

        for conn in query.limit(8).all():
            content_parts = [
                f"Interlock: {conn.source_tag} -> {conn.target_tag}"
            ]

            if conn.connection_type:
                content_parts.append(f"Type: {conn.connection_type}")
            if conn.function:
                content_parts.append(f"Function: {conn.function}")
            if conn.signal_type:
                content_parts.append(f"Signal: {conn.signal_type}")
            if conn.io_type:
                content_parts.append(f"IO: {conn.io_type}")

            # Parse details_json if available
            if conn.details_json:
                try:
                    details = json.loads(conn.details_json)
                    if "condition" in details:
                        content_parts.append(f"Condition: {details['condition']}")
                    if "action" in details:
                        content_parts.append(f"Action: {details['action']}")
                    if "trip_setpoint" in details:
                        content_parts.append(f"Trip Setpoint: {details['trip_setpoint']}")
                except (json.JSONDecodeError, TypeError):
                    pass

            results.append(AgentSearchResult(
                content="\n".join(content_parts),
                source_type="pdf",
                document_name=f"Document {conn.document_id}",
                page_or_location=f"Page {conn.page_number}",
                equipment_tag=tag,
                relevance_score=0.9,
                metadata={
                    "category": "INTERLOCK",
                    "connection_id": conn.id
                }
            ))

        return results

    def _search_safety_chunks(
        self,
        db: Session,
        query: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Semantic search for alarm and safety content in supplementary docs"""
        results = []

        # Enhance query with safety-related terms
        enhanced_query = f"{query} alarm interlock trip safety shutdown permissive"
        query_embedding = embedding_service.generate_embedding(enhanced_query)

        sql = text("""
            SELECT
                sc.id,
                sc.document_id,
                sc.content,
                sc.source_location,
                sc.equipment_tags,
                sd.original_filename,
                1 - (sc.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM supplementary_chunks sc
            JOIN supplementary_documents sd ON sc.document_id = sd.id
            WHERE sc.embedding IS NOT NULL
            AND (
                sc.content ILIKE '%alarm%'
                OR sc.content ILIKE '%interlock%'
                OR sc.content ILIKE '%trip%'
                OR sc.content ILIKE '%safety%'
                OR sc.content ILIKE '%shutdown%'
                OR sc.content ILIKE '%permissive%'
            )
            AND (:project_id IS NULL OR sd.project_id = :project_id)
            ORDER BY sc.embedding <=> CAST(:embedding AS vector)
            LIMIT 5
        """)

        params = {"embedding": str(query_embedding), "project_id": project_id}

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
                content=(row.content[:500] if len(row.content) > 500 else row.content) if row.content else "",
                source_type="supplementary",
                document_name=row.original_filename,
                page_or_location=row.source_location or "",
                equipment_tag=equipment_tag,
                relevance_score=float(row.similarity),
                metadata={}
            ))

        return results
