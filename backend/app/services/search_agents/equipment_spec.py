"""
Equipment Specification Agent

Specialized agent for equipment specifications, ratings, locations, and physical details.
Searches Equipment table, EquipmentData (SPECIFICATION), and PDF pages.
"""

import json
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import (
    Equipment, EquipmentLocation, EquipmentData, Page, Document,
    SupplementaryDocument
)
from app.services.search_agents.base import SearchAgent, AgentSearchResult

logger = logging.getLogger(__name__)

EQUIPMENT_SPEC_PROMPT = """You are an equipment specification expert analyzing industrial/electrical equipment.

Your expertise includes:
- Equipment tags, names, and identifiers
- HP/kW ratings and electrical specifications
- Voltages, phases, and frequencies
- Manufacturers and model numbers
- Physical locations and installation details
- Equipment types (motors, VFDs, pumps, fans, breakers, etc.)

Focus on extracting and presenting:
1. Equipment identification (tag, type, manufacturer, model)
2. Electrical ratings (HP, kW, voltage, amperage, phases)
3. Physical details (location, area, system)
4. Installation information from drawings

Be precise with technical values. If specifications are partial, note what's available and what's missing.
Always cite the source document and page/location for each piece of information."""


class EquipmentSpecAgent(SearchAgent):
    """Agent specialized in equipment specifications and ratings"""

    def __init__(self):
        super().__init__(
            name="EquipmentSpecAgent",
            domain="equipment_specifications"
        )

    def get_system_prompt(self) -> str:
        return EQUIPMENT_SPEC_PROMPT

    def search(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """
        Search for equipment specifications.

        Strategy:
        1. Direct equipment lookup for tags mentioned
        2. Search EquipmentData for SPECIFICATION type entries
        3. Search PDF pages for equipment details
        """
        results = []

        # 1. Direct equipment lookup
        for tag in equipment_tags:
            equipment = db.query(Equipment).filter(
                func.upper(Equipment.tag) == tag.upper()
            )
            if project_id:
                equipment = equipment.filter(Equipment.project_id == project_id)
            equipment = equipment.first()

            if equipment:
                # Build content from equipment record
                content_parts = [f"Equipment Tag: {equipment.tag}"]
                if equipment.equipment_type:
                    content_parts.append(f"Type: {equipment.equipment_type}")
                if equipment.description:
                    content_parts.append(f"Description: {equipment.description}")
                if equipment.manufacturer:
                    content_parts.append(f"Manufacturer: {equipment.manufacturer}")
                if equipment.model_number:
                    content_parts.append(f"Model: {equipment.model_number}")

                doc_name = "Equipment Database"
                if equipment.document:
                    doc_name = equipment.document.filename

                results.append(AgentSearchResult(
                    content="\n".join(content_parts),
                    source_type="equipment_db",
                    document_name=doc_name,
                    page_or_location=f"Page {equipment.primary_page}" if equipment.primary_page else "",
                    equipment_tag=equipment.tag,
                    relevance_score=1.0,
                    metadata={"equipment_id": equipment.id}
                ))

                # Also get locations
                locations = db.query(EquipmentLocation).filter(
                    EquipmentLocation.equipment_id == equipment.id
                ).join(Page).join(Document).all()

                for loc in locations[:3]:  # Limit to 3 locations
                    if loc.context_text:
                        results.append(AgentSearchResult(
                            content=loc.context_text,
                            source_type="pdf",
                            document_name=loc.page.document.filename,
                            page_or_location=f"Page {loc.page.page_number}",
                            equipment_tag=equipment.tag,
                            relevance_score=0.9,
                            metadata={
                                "document_id": loc.page.document.id,
                                "page_id": loc.page.id
                            }
                        ))

        # 2. Search EquipmentData for specifications
        for tag in equipment_tags:
            eq_data_query = db.query(EquipmentData).join(SupplementaryDocument).filter(
                EquipmentData.equipment_tag.ilike(f"%{tag}%"),
                EquipmentData.data_type == "SPECIFICATION"
            )
            if project_id:
                eq_data_query = eq_data_query.filter(
                    SupplementaryDocument.project_id == project_id
                )

            for entry in eq_data_query.limit(5).all():
                try:
                    data = json.loads(entry.data_json)
                    content = f"Specification for {entry.equipment_tag}:\n"
                    content += "\n".join(f"  {k}: {v}" for k, v in data.items())

                    results.append(AgentSearchResult(
                        content=content,
                        source_type="supplementary",
                        document_name=entry.document.original_filename,
                        page_or_location=entry.source_location or "",
                        equipment_tag=entry.equipment_tag,
                        relevance_score=entry.match_confidence or 0.85,
                        metadata={"data_type": entry.data_type}
                    ))
                except (json.JSONDecodeError, TypeError):
                    continue

        # 3. Search PDF pages with AI analysis for equipment info
        if equipment_tags and len(results) < 10:
            for tag in equipment_tags[:2]:  # Limit to first 2 tags
                pages_query = db.query(Page).join(Document).filter(
                    Page.ai_equipment_list.ilike(f"%{tag}%")
                )
                if project_id:
                    pages_query = pages_query.filter(Document.project_id == project_id)

                for page in pages_query.limit(3).all():
                    # Try to extract relevant section from AI analysis
                    content = ""
                    if page.ai_analysis:
                        content = page.ai_analysis[:500]
                    elif page.ocr_text:
                        content = page.ocr_text[:500]

                    if content:
                        results.append(AgentSearchResult(
                            content=content,
                            source_type="pdf",
                            document_name=page.document.filename,
                            page_or_location=f"Page {page.page_number}",
                            equipment_tag=tag,
                            relevance_score=0.7,
                            metadata={
                                "document_id": page.document.id,
                                "drawing_type": page.drawing_type
                            }
                        ))

        return results[:10]  # Limit total results
