"""
Relationship Agent

Specialized agent for power feeds, control loops, and equipment connections.
Uses DetailedConnection table and graph traversal for relationship queries.
"""

import logging
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import (
    Equipment, EquipmentRelationship, DetailedConnection, Document
)
from app.services.search_agents.base import SearchAgent, AgentSearchResult
from app.services.graph_service import graph_service

logger = logging.getLogger(__name__)

RELATIONSHIP_PROMPT = """You are a systems relationship expert analyzing industrial power and control systems.

Your expertise includes:
- Power distribution and feeds (what powers what)
- Control relationships (what controls what)
- Upstream and downstream equipment chains
- Electrical connections with voltages, breakers, and wire sizes
- Control signals with types (4-20mA, 0-10V, 24VDC, etc.)
- Protection and interlock relationships

Focus on:
1. Clear hierarchical relationships (source -> target)
2. Connection details (voltage, breaker, wire size, signal type)
3. Complete power/control chains when available
4. Document references for each relationship

Present relationships clearly showing the direction of power flow or control.
Use technical terminology for connection types and signal specifications."""


class RelationshipAgent(SearchAgent):
    """Agent specialized in equipment relationships and connections"""

    def __init__(self):
        super().__init__(
            name="RelationshipAgent",
            domain="equipment_relationships"
        )

    def get_system_prompt(self) -> str:
        return RELATIONSHIP_PROMPT

    def search(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """
        Search for equipment relationships.

        Strategy:
        1. Use graph_service to get equipment connections
        2. Query DetailedConnection for rich connection data
        3. Query EquipmentRelationship for basic relationships
        """
        results = []

        for tag in equipment_tags:
            # 1. Get full connection graph from graph_service
            connections = graph_service.get_equipment_connections(db, tag)
            graph_context = self._format_graph_connections(connections)

            if graph_context:
                results.append(AgentSearchResult(
                    content=graph_context,
                    source_type="graph",
                    document_name="Equipment Relationship Graph",
                    page_or_location="",
                    equipment_tag=tag,
                    relevance_score=1.0,
                    metadata={"source": "graph_service"}
                ))

            # 2. Get detailed connections for richer data
            detailed_conns = self._get_detailed_connections(db, tag, project_id)
            for conn_result in detailed_conns:
                results.append(conn_result)

            # 3. Get power flow if this seems like a power-related query
            query_lower = query.lower()
            if any(word in query_lower for word in ["feed", "power", "upstream", "downstream"]):
                power_flow = graph_service.get_full_power_flow(db, tag)
                flow_context = self._format_power_flow(power_flow)
                if flow_context:
                    results.append(AgentSearchResult(
                        content=flow_context,
                        source_type="graph",
                        document_name="Power Flow Analysis",
                        page_or_location="",
                        equipment_tag=tag,
                        relevance_score=0.95,
                        metadata={"source": "power_flow"}
                    ))

        return results[:10]

    def _format_graph_connections(self, connections: Dict) -> str:
        """Format graph connections into readable context"""
        parts = []
        tag = connections.get("equipment_tag", "Unknown")

        if connections.get("equipment_info"):
            info = connections["equipment_info"]
            parts.append(f"Equipment: {info.get('tag', tag)} ({info.get('type', 'Unknown')})")
            if info.get("description"):
                parts.append(f"Description: {info['description']}")

        # Power relationships
        if connections.get("feeds_from"):
            parts.append("\nPOWERED BY:")
            for feed in connections["feeds_from"]:
                details = feed.get("details", {})
                line = f"  {feed['tag']}"
                if details.get("breaker"):
                    line += f" via breaker {details['breaker']}"
                if details.get("voltage"):
                    line += f" at {details['voltage']}"
                if details.get("wire_size"):
                    line += f", wire: {details['wire_size']}"
                parts.append(line)

        if connections.get("feeds_to"):
            parts.append("\nFEEDS:")
            for feed in connections["feeds_to"]:
                details = feed.get("details", {})
                line = f"  {feed['tag']}"
                if details.get("breaker"):
                    line += f" via breaker {details['breaker']}"
                if details.get("load"):
                    line += f" (load: {details['load']})"
                parts.append(line)

        # Control relationships
        if connections.get("controlled_by"):
            parts.append("\nCONTROLLED BY:")
            for ctrl in connections["controlled_by"]:
                details = ctrl.get("details", {})
                line = f"  {ctrl['tag']}"
                if details.get("signal_type"):
                    line += f" [{details['signal_type']}]"
                if details.get("io_type"):
                    line += f" ({details['io_type']})"
                if details.get("function"):
                    line += f" - {details['function']}"
                parts.append(line)

        if connections.get("controls"):
            parts.append("\nCONTROLS:")
            for ctrl in connections["controls"]:
                details = ctrl.get("details", {})
                line = f"  {ctrl['tag']}"
                if details.get("signal_type"):
                    line += f" [{details['signal_type']}]"
                if details.get("function"):
                    line += f" - {details['function']}"
                parts.append(line)

        # Protection
        if connections.get("protected_by"):
            parts.append("\nPROTECTED BY:")
            for prot in connections["protected_by"]:
                parts.append(f"  {prot['tag']}")

        # Monitoring
        if connections.get("monitored_by"):
            parts.append("\nMONITORED BY:")
            for mon in connections["monitored_by"]:
                details = mon.get("details", {})
                line = f"  {mon['tag']}"
                if details.get("signal_type"):
                    line += f" [{details['signal_type']}]"
                parts.append(line)

        # Drives
        if connections.get("driven_by"):
            parts.append("\nDRIVEN BY:")
            for drv in connections["driven_by"]:
                parts.append(f"  {drv['tag']}")

        if connections.get("drives"):
            parts.append("\nDRIVES:")
            for drv in connections["drives"]:
                parts.append(f"  {drv['tag']}")

        return "\n".join(parts) if parts else ""

    def _format_power_flow(self, power_flow: Dict) -> str:
        """Format power flow analysis into readable context"""
        parts = []
        tag = power_flow.get("equipment_tag", "Unknown")

        if power_flow.get("upstream_tree"):
            parts.append(f"UPSTREAM POWER CHAIN for {tag}:")
            # Group by depth
            by_depth = {}
            for node in power_flow["upstream_tree"]:
                depth = node.get("depth", 0)
                if depth not in by_depth:
                    by_depth[depth] = []
                by_depth[depth].append(node)

            for depth in sorted(by_depth.keys()):
                for node in by_depth[depth]:
                    indent = "  " * depth
                    line = f"{indent}{node['tag']}"
                    if node.get("breaker"):
                        line += f" (breaker: {node['breaker']})"
                    if node.get("voltage"):
                        line += f" [{node['voltage']}]"
                    line += f" -> feeds {node.get('feeds', '?')}"
                    parts.append(line)

        if power_flow.get("downstream_tree"):
            parts.append(f"\nDOWNSTREAM EQUIPMENT fed by {tag}:")
            by_depth = {}
            for node in power_flow["downstream_tree"]:
                depth = node.get("depth", 0)
                if depth not in by_depth:
                    by_depth[depth] = []
                by_depth[depth].append(node)

            for depth in sorted(by_depth.keys()):
                for node in by_depth[depth]:
                    indent = "  " * depth
                    line = f"{indent}{node['tag']}"
                    if node.get("breaker"):
                        line += f" (breaker: {node['breaker']})"
                    if node.get("load"):
                        line += f" [load: {node['load']}]"
                    parts.append(line)

        if parts:
            parts.append(f"\nTotal: {power_flow.get('total_upstream', 0)} upstream, "
                        f"{power_flow.get('total_downstream', 0)} downstream")

        return "\n".join(parts) if parts else ""

    def _get_detailed_connections(
        self,
        db: Session,
        tag: str,
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """Get detailed connection records with document references"""
        results = []
        tag_upper = tag.upper()

        # Get connections where this equipment is source or target
        query = db.query(DetailedConnection).join(Document).filter(
            (func.upper(DetailedConnection.source_tag) == tag_upper) |
            (func.upper(DetailedConnection.target_tag) == tag_upper)
        )
        if project_id:
            query = query.filter(Document.project_id == project_id)

        connections = query.limit(10).all()

        for conn in connections:
            content_parts = [
                f"Connection: {conn.source_tag} -> {conn.target_tag}",
                f"Category: {conn.category}",
                f"Type: {conn.connection_type}"
            ]

            if conn.voltage:
                content_parts.append(f"Voltage: {conn.voltage}")
            if conn.breaker:
                content_parts.append(f"Breaker: {conn.breaker}")
            if conn.wire_size:
                content_parts.append(f"Wire Size: {conn.wire_size}")
            if conn.signal_type:
                content_parts.append(f"Signal: {conn.signal_type}")
            if conn.io_type:
                content_parts.append(f"IO Type: {conn.io_type}")
            if conn.function:
                content_parts.append(f"Function: {conn.function}")
            if conn.load:
                content_parts.append(f"Load: {conn.load}")

            doc = db.query(Document).filter(Document.id == conn.document_id).first()
            doc_name = doc.filename if doc else f"Document {conn.document_id}"

            results.append(AgentSearchResult(
                content="\n".join(content_parts),
                source_type="pdf",
                document_name=doc_name,
                page_or_location=f"Page {conn.page_number}",
                equipment_tag=tag,
                relevance_score=0.9,
                metadata={
                    "document_id": conn.document_id,
                    "connection_id": conn.id,
                    "category": conn.category
                }
            ))

        return results
