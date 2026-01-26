"""
Graph Service for Equipment Relationship Queries

Provides graph traversal capabilities for answering questions like:
- "What feeds VFD-101?"
- "What does PLC-1 control?"
- "What protects pump P-101?"
"""

import re
import json
import logging
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.database import Equipment, EquipmentRelationship, DetailedConnection, Document

logger = logging.getLogger(__name__)


# Patterns to identify relationship questions
RELATIONSHIP_QUESTION_PATTERNS = {
    "feeds": ["what feeds", "fed by", "fed from", "power source", "powered by", "supply"],
    "controls": ["what controls", "controlled by", "who controls", "controller for"],
    "protects": ["what protects", "protected by", "protection for", "trips"],
    "connects": ["connected to", "connects to", "what connects", "piped to", "wired to"],
    "drives": ["what drives", "driven by", "motor for"],
    "monitors": ["what monitors", "monitored by", "sensor for", "measures"],
}


class GraphService:
    """Service for querying equipment relationship graphs"""

    def extract_equipment_from_query(self, query: str, db: Session) -> List[str]:
        """Extract equipment tags mentioned in a query"""
        query_upper = query.upper()

        # Get all equipment tags from equipment table
        all_equipment = db.query(Equipment.tag).distinct().all()
        equipment_tags = [e[0] for e in all_equipment if e[0]]

        # Also get tags from detailed_connections table
        source_tags = db.query(DetailedConnection.source_tag).distinct().all()
        target_tags = db.query(DetailedConnection.target_tag).distinct().all()
        connection_tags = set([t[0] for t in source_tags if t[0]] + [t[0] for t in target_tags if t[0]])
        equipment_tags.extend(connection_tags)
        equipment_tags = list(set(equipment_tags))

        # Sort by length (longest first) to match longer tags first
        equipment_tags.sort(key=len, reverse=True)

        found_tags = []
        temp_query = query_upper

        for tag in equipment_tags:
            tag_upper = tag.upper()
            # Use word boundary matching
            pattern = r'\b' + re.escape(tag_upper) + r'\b'
            if re.search(pattern, temp_query):
                found_tags.append(tag)
                # Remove matched tag to avoid sub-matches
                temp_query = re.sub(pattern, '', temp_query)

        # Also try common equipment patterns if no matches found
        if not found_tags:
            generic_patterns = [
                r'\b([A-Z]{2,4}-[A-Z0-9]{1,4})\b',  # VFD-101, PLC-1
                r'\b([A-Z]{2,4}\s*[A-Z]?\d{2,4})\b',  # RTU F04, MCC 1
            ]
            for pattern in generic_patterns:
                matches = re.findall(pattern, query_upper)
                found_tags.extend(matches)

        return list(set(found_tags))

    def detect_relationship_type(self, query: str) -> Optional[str]:
        """Detect what type of relationship the user is asking about"""
        query_lower = query.lower()

        for rel_type, patterns in RELATIONSHIP_QUESTION_PATTERNS.items():
            for pattern in patterns:
                if pattern in query_lower:
                    return rel_type

        return None

    def get_equipment_connections(
        self,
        db: Session,
        equipment_tag: str,
        connection_types: List[str] = None,
        depth: int = 1
    ) -> Dict:
        """
        Get all connections for an equipment tag.

        Returns a dict with:
        - equipment: The equipment details
        - feeds_from: What feeds this equipment (upstream power)
        - feeds_to: What this equipment feeds (downstream power)
        - controlled_by: What controls this equipment
        - controls: What this equipment controls
        - protected_by: What protects this equipment
        - protects: What this equipment protects
        - connected_to: Mechanical/piping connections
        - detailed_connections: Full connection details with wire/pipe info
        """
        tag_upper = equipment_tag.upper()

        result = {
            "equipment_tag": equipment_tag,
            "feeds_from": [],
            "feeds_to": [],
            "controlled_by": [],
            "controls": [],
            "protected_by": [],
            "protects": [],
            "monitors": [],
            "monitored_by": [],
            "connected_to": [],
            "drives": [],
            "driven_by": [],
            "detailed_connections": []
        }

        # Get detailed connections where this equipment is source
        source_connections = db.query(DetailedConnection).filter(
            func.upper(DetailedConnection.source_tag) == tag_upper
        ).all()

        for conn in source_connections:
            conn_dict = self._connection_to_dict(conn)
            result["detailed_connections"].append(conn_dict)

            # Categorize by type
            conn_type = (conn.connection_type or "").upper()
            category = (conn.category or "").upper()

            if conn_type == "FEEDS" or category == "ELECTRICAL" and "FEEDS" in conn_type:
                result["feeds_to"].append({
                    "tag": conn.target_tag,
                    "details": conn_dict
                })
            elif conn_type in ["CONTROLS", "AO", "DO"] or category == "CONTROL":
                result["controls"].append({
                    "tag": conn.target_tag,
                    "details": conn_dict
                })
            elif conn_type == "PROTECTS":
                result["protects"].append({
                    "tag": conn.target_tag,
                    "details": conn_dict
                })
            elif conn_type == "MONITORS":
                result["monitors"].append({
                    "tag": conn.target_tag,
                    "details": conn_dict
                })
            elif conn_type == "DRIVES":
                result["drives"].append({
                    "tag": conn.target_tag,
                    "details": conn_dict
                })
            elif category == "MECHANICAL":
                result["connected_to"].append({
                    "tag": conn.target_tag,
                    "details": conn_dict
                })

        # Get detailed connections where this equipment is target
        target_connections = db.query(DetailedConnection).filter(
            func.upper(DetailedConnection.target_tag) == tag_upper
        ).all()

        for conn in target_connections:
            conn_dict = self._connection_to_dict(conn)
            result["detailed_connections"].append(conn_dict)

            conn_type = (conn.connection_type or "").upper()
            category = (conn.category or "").upper()

            if conn_type == "FEEDS" or category == "ELECTRICAL" and "FEEDS" in conn_type:
                result["feeds_from"].append({
                    "tag": conn.source_tag,
                    "details": conn_dict
                })
            elif conn_type in ["CONTROLS", "AO", "DO"] or category == "CONTROL":
                result["controlled_by"].append({
                    "tag": conn.source_tag,
                    "details": conn_dict
                })
            elif conn_type == "PROTECTS":
                result["protected_by"].append({
                    "tag": conn.source_tag,
                    "details": conn_dict
                })
            elif conn_type in ["MONITORS", "AI", "DI"]:
                result["monitored_by"].append({
                    "tag": conn.source_tag,
                    "details": conn_dict
                })
            elif conn_type == "DRIVES":
                result["driven_by"].append({
                    "tag": conn.source_tag,
                    "details": conn_dict
                })
            elif category == "MECHANICAL":
                result["connected_to"].append({
                    "tag": conn.source_tag,
                    "details": conn_dict
                })

        # Also check equipment_relationships table for additional relationships
        equipment = db.query(Equipment).filter(
            func.upper(Equipment.tag) == tag_upper
        ).first()

        if equipment:
            result["equipment_info"] = {
                "tag": equipment.tag,
                "type": equipment.equipment_type,
                "description": equipment.description
            }

            # Get relationships from equipment_relationships table
            for rel in equipment.controls:
                target = db.query(Equipment).filter(Equipment.id == rel.target_id).first()
                if target and not any(c["tag"].upper() == target.tag.upper() for c in result["controls"]):
                    result["controls"].append({
                        "tag": target.tag,
                        "details": {
                            "relationship_type": rel.relationship_type,
                            "confidence": rel.confidence
                        }
                    })

            for rel in equipment.controlled_by:
                source = db.query(Equipment).filter(Equipment.id == rel.source_id).first()
                if source:
                    rel_type = rel.relationship_type.upper()
                    if rel_type == "POWERS" and not any(c["tag"].upper() == source.tag.upper() for c in result["feeds_from"]):
                        result["feeds_from"].append({
                            "tag": source.tag,
                            "details": {"relationship_type": rel.relationship_type}
                        })
                    elif rel_type == "CONTROLS" and not any(c["tag"].upper() == source.tag.upper() for c in result["controlled_by"]):
                        result["controlled_by"].append({
                            "tag": source.tag,
                            "details": {"relationship_type": rel.relationship_type}
                        })

        return result

    def _connection_to_dict(self, conn: DetailedConnection) -> Dict:
        """Convert a DetailedConnection to a dictionary"""
        return {
            "source": conn.source_tag,
            "target": conn.target_tag,
            "category": conn.category,
            "connection_type": conn.connection_type,
            "voltage": conn.voltage,
            "breaker": conn.breaker,
            "wire_size": conn.wire_size,
            "wire_numbers": json.loads(conn.wire_numbers) if conn.wire_numbers else None,
            "load": conn.load,
            "signal_type": conn.signal_type,
            "io_type": conn.io_type,
            "point_name": conn.point_name,
            "function": conn.function,
            "medium": conn.medium,
            "pipe_size": conn.pipe_size,
            "inline_devices": json.loads(conn.inline_devices) if conn.inline_devices else None,
            "page_number": conn.page_number,
            "document_id": conn.document_id
        }

    def build_graph_context(self, db: Session, equipment_tags: List[str], query: str) -> str:
        """
        Build a rich context string for the LLM based on equipment graph data.
        """
        if not equipment_tags:
            return ""

        parts = []
        rel_type = self.detect_relationship_type(query)

        for tag in equipment_tags[:3]:  # Limit to first 3 equipment tags
            connections = self.get_equipment_connections(db, tag)

            parts.append(f"\n=== EQUIPMENT GRAPH FOR {tag} ===")

            if connections.get("equipment_info"):
                info = connections["equipment_info"]
                parts.append(f"Type: {info.get('type', 'Unknown')}")
                if info.get("description"):
                    parts.append(f"Description: {info['description'][:200]}")

            # Power/Feed relationships
            if connections["feeds_from"]:
                parts.append(f"\nPOWERED BY (Upstream):")
                for feed in connections["feeds_from"]:
                    details = feed.get("details", {})
                    line = f"  - {feed['tag']}"
                    if details.get("breaker"):
                        line += f" via {details['breaker']}"
                    if details.get("voltage"):
                        line += f" ({details['voltage']})"
                    if details.get("wire_size"):
                        line += f", Wire: {details['wire_size']}"
                    parts.append(line)

            if connections["feeds_to"]:
                parts.append(f"\nFEEDS (Downstream):")
                for feed in connections["feeds_to"]:
                    details = feed.get("details", {})
                    line = f"  - {feed['tag']}"
                    if details.get("breaker"):
                        line += f" via {details['breaker']}"
                    if details.get("voltage"):
                        line += f" ({details['voltage']})"
                    if details.get("load"):
                        line += f", Load: {details['load']}"
                    parts.append(line)

            # Control relationships
            if connections["controlled_by"]:
                parts.append(f"\nCONTROLLED BY:")
                for ctrl in connections["controlled_by"]:
                    details = ctrl.get("details", {})
                    line = f"  - {ctrl['tag']}"
                    if details.get("signal_type"):
                        line += f" ({details['signal_type']})"
                    if details.get("io_type"):
                        line += f" [{details['io_type']}]"
                    if details.get("function"):
                        line += f" - {details['function']}"
                    if details.get("wire_numbers"):
                        line += f", Wires: {details['wire_numbers']}"
                    parts.append(line)

            if connections["controls"]:
                parts.append(f"\nCONTROLS:")
                for ctrl in connections["controls"]:
                    details = ctrl.get("details", {})
                    line = f"  - {ctrl['tag']}"
                    if details.get("signal_type"):
                        line += f" ({details['signal_type']})"
                    if details.get("function"):
                        line += f" - {details['function']}"
                    parts.append(line)

            # Protection
            if connections["protected_by"]:
                parts.append(f"\nPROTECTED BY:")
                for prot in connections["protected_by"]:
                    parts.append(f"  - {prot['tag']}")

            if connections["protects"]:
                parts.append(f"\nPROTECTS:")
                for prot in connections["protects"]:
                    parts.append(f"  - {prot['tag']}")

            # Monitoring
            if connections["monitored_by"]:
                parts.append(f"\nMONITORED BY (Sensors):")
                for mon in connections["monitored_by"]:
                    details = mon.get("details", {})
                    line = f"  - {mon['tag']}"
                    if details.get("signal_type"):
                        line += f" ({details['signal_type']})"
                    if details.get("function"):
                        line += f" - {details['function']}"
                    parts.append(line)

            # Mechanical/Piping
            if connections["connected_to"]:
                parts.append(f"\nMECHANICAL CONNECTIONS:")
                for conn in connections["connected_to"]:
                    details = conn.get("details", {})
                    line = f"  - {conn['tag']}"
                    if details.get("medium"):
                        line += f" via {details['medium']}"
                    if details.get("pipe_size"):
                        line += f" ({details['pipe_size']})"
                    if details.get("inline_devices"):
                        devices = [d.get("tag", "") for d in details["inline_devices"]]
                        line += f", Inline: {', '.join(devices)}"
                    parts.append(line)

            # Drives
            if connections["driven_by"]:
                parts.append(f"\nDRIVEN BY:")
                for drv in connections["driven_by"]:
                    parts.append(f"  - {drv['tag']}")

            if connections["drives"]:
                parts.append(f"\nDRIVES:")
                for drv in connections["drives"]:
                    parts.append(f"  - {drv['tag']}")

        return "\n".join(parts)

    def get_full_power_flow(self, db: Session, equipment_tag: str, max_depth: int = 10) -> Dict:
        """
        BFS traversal for complete power hierarchy with support for multi-branch power distribution.

        Args:
            db: Database session
            equipment_tag: Starting equipment tag
            max_depth: Maximum traversal depth

        Returns:
            Dict with upstream_tree, downstream_tree, and metadata
        """
        tag_upper = equipment_tag.upper()

        result = {
            "equipment_tag": equipment_tag,
            "upstream_tree": [],
            "downstream_tree": [],
            "total_upstream": 0,
            "total_downstream": 0
        }

        # BFS for upstream (what feeds this equipment)
        upstream_queue = [(tag_upper, 0, None)]  # (tag, depth, parent_tag)
        upstream_visited = set()

        while upstream_queue:
            current, depth, parent = upstream_queue.pop(0)
            if current in upstream_visited or depth > max_depth:
                continue
            upstream_visited.add(current)

            # Get ALL feeds to this equipment (not .first()!)
            feeds = db.query(DetailedConnection).filter(
                func.upper(DetailedConnection.target_tag) == current,
                DetailedConnection.category == "ELECTRICAL",
                DetailedConnection.connection_type == "FEEDS"
            ).all()

            for feed in feeds:
                source_tag = feed.source_tag.upper()
                node = {
                    "tag": feed.source_tag,
                    "feeds": current,
                    "depth": depth + 1,
                    "breaker": feed.breaker,
                    "voltage": feed.voltage,
                    "wire_size": feed.wire_size,
                    "load": feed.load,
                    "document_id": feed.document_id,
                    "page_number": feed.page_number
                }
                result["upstream_tree"].append(node)
                upstream_queue.append((source_tag, depth + 1, current))

        # BFS for downstream (what this equipment feeds)
        downstream_queue = [(tag_upper, 0, None)]
        downstream_visited = set()

        while downstream_queue:
            current, depth, parent = downstream_queue.pop(0)
            if current in downstream_visited or depth > max_depth:
                continue
            downstream_visited.add(current)

            # Get ALL equipment fed by this one
            fed_equipment = db.query(DetailedConnection).filter(
                func.upper(DetailedConnection.source_tag) == current,
                DetailedConnection.category == "ELECTRICAL",
                DetailedConnection.connection_type == "FEEDS"
            ).all()

            for feed in fed_equipment:
                target_tag = feed.target_tag.upper()
                node = {
                    "tag": feed.target_tag,
                    "fed_by": current,
                    "depth": depth + 1,
                    "breaker": feed.breaker,
                    "voltage": feed.voltage,
                    "wire_size": feed.wire_size,
                    "load": feed.load,
                    "document_id": feed.document_id,
                    "page_number": feed.page_number
                }
                result["downstream_tree"].append(node)
                downstream_queue.append((target_tag, depth + 1, current))

        result["total_upstream"] = len(result["upstream_tree"])
        result["total_downstream"] = len(result["downstream_tree"])

        return result

    def get_power_chain(self, db: Session, equipment_tag: str, direction: str = "upstream", depth: int = 5) -> List[Dict]:
        """
        Trace the power chain upstream or downstream from an equipment.

        Args:
            equipment_tag: Starting equipment tag
            direction: "upstream" (what feeds this) or "downstream" (what this feeds)
            depth: Maximum depth to traverse

        Returns:
            List of equipment in the chain with connection details
        """
        chain = []
        visited = set()
        current_tag = equipment_tag.upper()

        for _ in range(depth):
            if current_tag in visited:
                break
            visited.add(current_tag)

            if direction == "upstream":
                # Find what feeds this equipment
                conn = db.query(DetailedConnection).filter(
                    func.upper(DetailedConnection.target_tag) == current_tag,
                    DetailedConnection.category == "ELECTRICAL",
                    DetailedConnection.connection_type == "FEEDS"
                ).first()
            else:
                # Find what this equipment feeds
                conn = db.query(DetailedConnection).filter(
                    func.upper(DetailedConnection.source_tag) == current_tag,
                    DetailedConnection.category == "ELECTRICAL",
                    DetailedConnection.connection_type == "FEEDS"
                ).first()

            if conn:
                chain.append({
                    "tag": conn.source_tag if direction == "upstream" else conn.target_tag,
                    "breaker": conn.breaker,
                    "voltage": conn.voltage,
                    "wire_size": conn.wire_size
                })
                current_tag = (conn.source_tag if direction == "upstream" else conn.target_tag).upper()
            else:
                break

        return chain


# Singleton instance
graph_service = GraphService()
