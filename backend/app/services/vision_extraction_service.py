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
        # Ensure image is loaded into memory (thread-safe)
        if hasattr(page_image, "load"):
             page_image.load()

        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_relationships = []
        
        def analyze_single(eq):
            tag = eq.get("tag")
            bbox = eq.get("bbox")
            
            if not tag or not bbox:
                return []
                
            try:
                # Create crop
                crop = self.preprocessor.create_centered_crop(page_image, bbox)
                
                # Analyze crop
                result = self.client.analyze_crop(crop, tag)
                
                found = []
                if result and "relationships" in result:
                    for rel in result["relationships"]:
                        # Convert string confidence to float
                        conf_str = str(rel.get("confidence", "medium")).lower()
                        conf_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
                        conf_val = conf_map.get(conf_str, 0.7)
                        
                        found.append({
                            "source": tag,
                            "target": rel.get("target"),
                            "type": rel.get("type"),
                            "confidence": conf_val,
                            "method": "vision",
                            "raw_data": rel
                        })
                        logger.info(f"Vision found: {tag} -> {rel.get('target')} ({rel.get('type')})")
                return found
            except Exception as e:
                logger.error(f"Error processing {tag}: {e}")
                return []

        # Run in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(analyze_single, eq) for eq in equipment_list]
            for future in as_completed(futures):
                try:
                    rels = future.result()
                    all_relationships.extend(rels)
                except Exception as e:
                    logger.error(f"Thread error: {e}")
                    
        return all_relationships

vision_extraction_service = VisionExtractionService()
