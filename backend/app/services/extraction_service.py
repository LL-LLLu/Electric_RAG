import re
import logging
from typing import List, Dict
from dataclasses import dataclass

from app.utils.tag_patterns import (
    EQUIPMENT_PATTERNS, WIRE_PATTERNS,
    CONTROL_KEYWORDS, POWER_KEYWORDS
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEquipment:
    tag: str
    equipment_type: str
    context: str
    bbox: Dict = None
    confidence: float = 1.0


class ExtractionService:
    """Extract equipment tags, wire numbers, and relationships from OCR text"""

    def extract_equipment_tags(self, text: str, elements: List[Dict] = None) -> List[ExtractedEquipment]:
        """Extract all equipment tags from text"""
        found_equipment: Dict[str, ExtractedEquipment] = {}

        for pattern, equip_type in EQUIPMENT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                tag = match.group(0).upper()

                if tag in found_equipment:
                    continue

                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()

                bbox = None
                if elements:
                    bbox = self._find_bbox_for_tag(tag, elements)

                found_equipment[tag] = ExtractedEquipment(
                    tag=tag,
                    equipment_type=equip_type,
                    context=context,
                    bbox=bbox
                )

        return list(found_equipment.values())

    def extract_wire_numbers(self, text: str) -> List[str]:
        """Extract wire numbers from text"""
        wires = set()

        for pattern in WIRE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            wires.update([w.upper() for w in matches])

        return list(wires)

    def extract_relationships(self, text: str, equipment_tags: List[str]) -> List[Dict]:
        """Extract relationships between equipment based on text context"""
        relationships = []

        if not equipment_tags:
            return relationships

        for keyword in CONTROL_KEYWORDS:
            pattern = rf'({"|".join(equipment_tags)})\s+{keyword}\s+({"|".join(equipment_tags)})'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                relationships.append({
                    "source": match.group(1).upper(),
                    "target": match.group(2).upper(),
                    "type": "CONTROLS",
                    "confidence": 0.8
                })

        for keyword in POWER_KEYWORDS:
            pattern = rf'({"|".join(equipment_tags)})\s+{keyword}\s+({"|".join(equipment_tags)})'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                relationships.append({
                    "source": match.group(1).upper(),
                    "target": match.group(2).upper(),
                    "type": "POWERS",
                    "confidence": 0.8
                })

        return relationships

    def _find_bbox_for_tag(self, tag: str, elements: List[Dict]) -> Dict:
        """Find bounding box for a tag in OCR elements"""
        for element in elements:
            if tag.upper() in element["text"].upper():
                return element["bbox"]
        return None

    def infer_equipment_type_from_context(self, tag: str, context: str) -> str:
        """Try to infer equipment type from surrounding context"""
        context_lower = context.lower()

        type_keywords = {
            'FAN': ['fan', 'air handler', 'exhaust', 'supply air', 'cfm'],
            'MOTOR': ['motor', 'hp', 'horsepower', 'rpm', 'kw'],
            'VFD': ['vfd', 'variable frequency', 'drive', 'inverter'],
            'PUMP': ['pump', 'gpm', 'head', 'flow'],
            'BREAKER': ['breaker', 'circuit', 'amp', 'disconnect'],
            'SENSOR': ['sensor', 'transmitter', 'temperature', 'pressure', 'level'],
            'VALVE': ['valve', 'actuator', 'damper'],
        }

        for equip_type, keywords in type_keywords.items():
            if any(kw in context_lower for kw in keywords):
                return equip_type

        return 'OTHER'


extraction_service = ExtractionService()
