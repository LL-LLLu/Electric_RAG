import re
import logging
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from fuzzywuzzy import fuzz

from app.models.database import Equipment, EquipmentAlias

logger = logging.getLogger(__name__)


class AliasService:
    """Service for fuzzy matching equipment tags and managing aliases"""

    MATCH_THRESHOLD = 85  # Minimum confidence for auto-matching

    def normalize_tag(self, tag: str) -> str:
        """Normalize tag for comparison: RTU-F04 → rtuf04"""
        if not tag:
            return ""
        # Remove separators and convert to lowercase
        return re.sub(r'[-_\s.]', '', tag.lower())

    def fuzzy_match(self, tag: str, equipment_list: List[Equipment]) -> Tuple[Optional[int], float]:
        """Find best matching equipment with confidence score

        Args:
            tag: The equipment tag to match
            equipment_list: List of Equipment objects to match against

        Returns:
            Tuple of (equipment_id or None, confidence 0.0-1.0)
        """
        if not tag or not equipment_list:
            return (None, 0.0)

        normalized = self.normalize_tag(tag)
        best_match = None
        best_score = 0

        for eq in equipment_list:
            # Compare normalized versions
            eq_normalized = self.normalize_tag(eq.tag)
            score = fuzz.ratio(normalized, eq_normalized)

            # Also check existing aliases
            if hasattr(eq, 'aliases') and eq.aliases:
                for alias in eq.aliases:
                    alias_score = fuzz.ratio(normalized, self.normalize_tag(alias.alias))
                    score = max(score, alias_score)

            if score > best_score:
                best_score = score
                best_match = eq

        # Return match if confidence >= threshold
        if best_score >= self.MATCH_THRESHOLD:
            return (best_match.id, best_score / 100.0)
        return (None, best_score / 100.0)

    def find_equipment_by_tag(self, db: Session, tag: str, project_id: int = None) -> Tuple[Optional[Equipment], float]:
        """Find equipment by tag with fuzzy matching

        Args:
            db: Database session
            tag: Equipment tag to find
            project_id: Optional project scope

        Returns:
            Tuple of (Equipment or None, confidence)
        """
        # First try exact match
        query = db.query(Equipment).filter(func.upper(Equipment.tag) == tag.upper())
        if project_id:
            query = query.filter(Equipment.project_id == project_id)
        equipment = query.first()

        if equipment:
            return (equipment, 1.0)

        # Try alias match
        alias_query = db.query(EquipmentAlias).join(Equipment).filter(
            func.upper(EquipmentAlias.alias) == tag.upper()
        )
        if project_id:
            alias_query = alias_query.filter(Equipment.project_id == project_id)
        alias = alias_query.first()

        if alias:
            equipment = db.query(Equipment).filter(Equipment.id == alias.equipment_id).first()
            return (equipment, alias.confidence or 0.9)

        # Fall back to fuzzy matching
        eq_query = db.query(Equipment)
        if project_id:
            eq_query = eq_query.filter(Equipment.project_id == project_id)
        equipment_list = eq_query.all()

        eq_id, confidence = self.fuzzy_match(tag, equipment_list)
        if eq_id:
            equipment = db.query(Equipment).filter(Equipment.id == eq_id).first()
            return (equipment, confidence)

        return (None, confidence)

    def create_alias(self, db: Session, equipment_id: int, alias: str,
                     source: str = None, confidence: float = None) -> EquipmentAlias:
        """Create an equipment alias

        Args:
            db: Database session
            equipment_id: Equipment to alias
            alias: The alias string
            source: Where this alias came from
            confidence: Match confidence

        Returns:
            Created EquipmentAlias
        """
        # Check if alias already exists for this equipment
        existing = db.query(EquipmentAlias).filter(
            EquipmentAlias.equipment_id == equipment_id,
            func.upper(EquipmentAlias.alias) == alias.upper()
        ).first()

        if existing:
            return existing

        new_alias = EquipmentAlias(
            equipment_id=equipment_id,
            alias=alias,
            source=source,
            confidence=confidence
        )
        db.add(new_alias)
        db.commit()
        db.refresh(new_alias)

        logger.info(f"Created alias '{alias}' for equipment ID {equipment_id}")
        return new_alias

    def get_equipment_by_alias(self, db: Session, alias: str, project_id: int = None) -> Optional[Equipment]:
        """Get equipment by its alias

        Args:
            db: Database session
            alias: Alias to look up
            project_id: Optional project scope

        Returns:
            Equipment if found, None otherwise
        """
        query = db.query(EquipmentAlias).join(Equipment).filter(
            func.upper(EquipmentAlias.alias) == alias.upper()
        )
        if project_id:
            query = query.filter(Equipment.project_id == project_id)

        alias_record = query.first()
        if alias_record:
            return db.query(Equipment).filter(Equipment.id == alias_record.equipment_id).first()
        return None

    def get_all_aliases(self, db: Session, equipment_id: int) -> List[EquipmentAlias]:
        """Get all aliases for an equipment

        Args:
            db: Database session
            equipment_id: Equipment ID

        Returns:
            List of EquipmentAlias objects
        """
        return db.query(EquipmentAlias).filter(
            EquipmentAlias.equipment_id == equipment_id
        ).all()


# Singleton instance
alias_service = AliasService()
