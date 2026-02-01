import os
import json
import logging
import google.generativeai as genai
from PIL import Image
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GeminiVisionClient:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-pro")
        else:
            self.model = None
            logger.warning("GEMINI_API_KEY not set")

    def analyze_crop(self, image: Image.Image, focus_tag: str) -> Dict[str, Any]:
        if not self.model:
            return {}
            
        prompt = f"""
        Analyze this engineering drawing crop. 
        Focus on the equipment labeled '{focus_tag}'.
        Visually trace the lines connected to '{focus_tag}'.
        
        Identify:
        1. What equipment is it connected to?
        2. What is the nature of the connection (line type)?
        3. Are there arrowheads indicating flow direction?
        
        Return JSON only:
        {{
            "relationships": [
                {{
                    "target": "TAG",
                    "type": "feeds/controls/connected_to",
                    "confidence": "high/medium/low",
                    "reasoning": "thick line with arrow pointing to target"
                }}
            ]
        }}
        """
        
        try:
            response = self.model.generate_content([prompt, image])
            text = response.text
            # Clean json
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
            return {}
        except Exception as e:
            logger.error(f"Gemini vision analysis failed: {e}")
            return {}
