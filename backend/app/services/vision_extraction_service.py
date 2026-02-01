import logging
from typing import List, Dict, Any
from PIL import Image
from app.services.vision.image_preprocessor import ImagePreprocessor
from app.services.vision.gemini_client import GeminiVisionClient

logger = logging.getLogger(__name__)

class VisionExtractionService:
    def __init__(self):
        self.preprocessor = ImagePreprocessor()
        self.client = GeminiVisionClient()
        
    def process_page(self, page_image: Image.Image, equipment_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a page image to find relationships for listed equipment.
        equipment_list: [{"tag": "MCC-1", "bbox": {...}}, ...]
        """
        all_relationships = []
        
        for eq in equipment_list:
            tag = eq.get("tag")
            bbox = eq.get("bbox")
            
            if not tag or not bbox:
                continue
                
            # Create crop
            crop = self.preprocessor.create_centered_crop(page_image, bbox)
            
            # Analyze crop
            result = self.client.analyze_crop(crop, tag)
            
            if result and "relationships" in result:
                for rel in result["relationships"]:
                    all_relationships.append({
                        "source": tag,
                        "target": rel.get("target"),
                        "type": rel.get("type"),
                        "confidence": rel.get("confidence", "medium"),
                        "method": "vision",
                        "raw_data": rel
                    })
                    logger.info(f"Vision found: {tag} -> {rel.get('target')} ({rel.get('type')})")
                    
        return all_relationships

vision_extraction_service = VisionExtractionService()
