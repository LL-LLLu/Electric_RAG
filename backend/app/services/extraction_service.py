import re
import logging
from typing import List, Dict
from dataclasses import dataclass

from app.utils.tag_patterns import (
    EQUIPMENT_PATTERNS, WIRE_PATTERNS,
    CONTROL_KEYWORDS, POWER_KEYWORDS
)

logger = logging.getLogger(__name__)

# Additional relationship keywords for AI parsing
RELATIONSHIP_PATTERNS = {
    "CONTROLS": ["controls", "operates", "starts", "stops", "runs", "enables", "activates"],
    "POWERS": ["powers", "feeds", "supplies", "energizes"],
    "FED_BY": ["fed by", "powered by", "supplied by", "fed from"],
    "CONTROLLED_BY": ["controlled by", "operated by", "started by", "stopped by"],
    "PROTECTS": ["protects", "trips", "disconnects", "isolates"],
    "PROTECTED_BY": ["protected by", "tripped by"],
    "MONITORS": ["monitors", "measures", "senses", "reads"],
    "CONNECTS_TO": ["connects to", "connected to", "wired to", "linked to"],
}


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

        # Filter out empty/None values and escape special regex characters
        valid_tags = [re.escape(tag) for tag in equipment_tags if tag and tag.strip()]
        if not valid_tags:
            return relationships

        tags_pattern = "|".join(valid_tags)

        for keyword in CONTROL_KEYWORDS:
            pattern = rf'({tags_pattern})\s+{keyword}\s+({tags_pattern})'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                source = match.group(1)
                target = match.group(2)
                if source and target:
                    relationships.append({
                        "source": source.upper(),
                        "target": target.upper(),
                        "type": "CONTROLS",
                        "confidence": 0.8
                    })

        for keyword in POWER_KEYWORDS:
            pattern = rf'({tags_pattern})\s+{keyword}\s+({tags_pattern})'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                source = match.group(1)
                target = match.group(2)
                if source and target:
                    relationships.append({
                        "source": source.upper(),
                        "target": target.upper(),
                        "type": "POWERS",
                        "confidence": 0.8
                    })

        return relationships

    def _find_bbox_for_tag(self, tag: str, elements: List[Dict]) -> Dict:
        """Find bounding box for a tag in OCR elements"""
        if not tag:
            return None
        for element in elements:
            if element.get("text") and tag.upper() in element["text"].upper():
                return element.get("bbox")
        return None

    def parse_ai_relationships(self, ai_relationships: List[str], equipment_tags: List[str]) -> List[Dict]:
        """Parse AI-detected relationship strings into structured data.

        Examples:
            "PLC-1 controls VFD-101" -> {source: PLC-1, target: VFD-101, type: CONTROLS}
            "VFD-101 is fed by MCC-1" -> {source: MCC-1, target: VFD-101, type: POWERS}
            "BKR-1 protects M-101" -> {source: BKR-1, target: M-101, type: PROTECTS}
            "BMS monitors DP SENSOR" -> {source: BMS, target: DP SENSOR, type: MONITORS}
        """
        relationships = []

        # Filter and prepare valid equipment tags
        valid_tags = [t.strip() for t in equipment_tags if t and t.strip()]
        if not valid_tags:
            return relationships

        # Sort tags by length (longest first) to match longer tags before shorter ones
        # e.g., "DP SENSOR" before "DP"
        sorted_tags = sorted(valid_tags, key=len, reverse=True)

        for rel_str in ai_relationships:
            if not rel_str:
                continue

            rel_lower = rel_str.lower()
            rel_upper = rel_str.upper()

            # Find equipment tags in the string by matching against known tags
            found_tags = []
            found_positions = []
            temp_str = rel_upper

            for tag in sorted_tags:
                tag_upper = tag.upper()
                # Use word boundary matching to avoid partial matches
                pattern = r'\b' + re.escape(tag_upper) + r'\b'
                match = re.search(pattern, temp_str)
                if match:
                    found_tags.append(tag_upper)
                    found_positions.append(match.start())
                    # Replace matched tag to avoid re-matching
                    temp_str = temp_str[:match.start()] + ('_' * len(tag_upper)) + temp_str[match.end():]

            if len(found_tags) < 2:
                # Fallback: try generic pattern for tags not in our list
                generic_pattern = r'\b([A-Z][A-Z0-9]*(?:[-_\s][A-Z0-9]+)*)\b'
                generic_matches = re.findall(generic_pattern, rel_upper)
                # Filter out common words
                common_words = {'THE', 'AND', 'FOR', 'FROM', 'WITH', 'BY', 'TO', 'IS', 'ARE', 'OF', 'IN', 'ON', 'AT'}
                generic_matches = [m for m in generic_matches if m not in common_words and len(m) >= 2]
                if len(generic_matches) >= 2:
                    found_tags = generic_matches[:2]
                    found_positions = [rel_upper.find(t) for t in found_tags]

            if len(found_tags) < 2:
                continue

            # Sort by position in string to get correct order
            tag_positions = list(zip(found_tags, found_positions))
            tag_positions.sort(key=lambda x: x[1])
            found_tags = [t[0] for t in tag_positions]

            # Determine relationship type and direction
            rel_type = None
            reverse = False

            for rtype, keywords in RELATIONSHIP_PATTERNS.items():
                for keyword in keywords:
                    if keyword in rel_lower:
                        rel_type = rtype
                        # Handle reverse relationships (fed by, controlled by)
                        if rtype in ["FED_BY", "CONTROLLED_BY", "PROTECTED_BY"]:
                            reverse = True
                            # Map to forward relationship type
                            if rtype == "FED_BY":
                                rel_type = "POWERS"
                            elif rtype == "CONTROLLED_BY":
                                rel_type = "CONTROLS"
                            elif rtype == "PROTECTED_BY":
                                rel_type = "PROTECTS"
                        break
                if rel_type:
                    break

            if not rel_type:
                rel_type = "CONNECTS_TO"  # Default relationship

            # Assign source and target based on direction
            if reverse:
                source = found_tags[1]
                target = found_tags[0]
            else:
                source = found_tags[0]
                target = found_tags[1]

            # Check if tags are in known equipment
            source_valid = any(t.upper() == source for t in valid_tags)
            target_valid = any(t.upper() == target for t in valid_tags)

            if source != target:  # Avoid self-relationships
                relationships.append({
                    "source": source,
                    "target": target,
                    "type": rel_type,
                    "confidence": 0.7 if (source_valid and target_valid) else 0.5,
                    "raw_text": rel_str
                })

        return relationships

    def infer_equipment_type_from_context(self, tag: str, context: str) -> str:
        """Try to infer equipment type from surrounding context"""
        context_lower = context.lower()

        type_keywords = {
            'RTU': ['rtu', 'remote terminal', 'terminal unit', 'scada'],
            'FAN': ['fan', 'air handler', 'exhaust', 'supply air', 'cfm'],
            'MOTOR': ['motor', 'hp', 'horsepower', 'rpm', 'kw'],
            'VFD': ['vfd', 'variable frequency', 'drive', 'inverter'],
            'PUMP': ['pump', 'gpm', 'head', 'flow'],
            'BREAKER': ['breaker', 'circuit', 'amp', 'disconnect'],
            'PLC': ['plc', 'programmable', 'controller', 'processor'],
            'SENSOR': ['sensor', 'transmitter', 'temperature', 'pressure', 'level'],
            'VALVE': ['valve', 'actuator', 'damper'],
            'PANEL': ['panel', 'mcc', 'switchgear', 'distribution'],
            'TRANSFORMER': ['transformer', 'xfmr', 'kva'],
            'HMI': ['hmi', 'operator interface', 'touch screen', 'display'],
        }

        for equip_type, keywords in type_keywords.items():
            if any(kw in context_lower for kw in keywords):
                return equip_type

        return 'OTHER'


extraction_service = ExtractionService()
