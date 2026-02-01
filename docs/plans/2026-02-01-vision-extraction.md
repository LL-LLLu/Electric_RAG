# Vision Extraction Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Implement a Vision-Language Model (VLM) based extraction pipeline to accurately trace equipment relationships in engineering drawings by "looking" at cropped sections around equipment.

**Architecture:** 
A `VisionExtractionService` orchestrates the process. It uses `ImagePreprocessor` to generate targeted image crops centered on equipment found by the existing OCR text extraction. These crops are sent to `GeminiVisionClient` (wrapping Gemini 1.5 Pro) with a prompt to visually trace lines. The results are merged with existing text-based relationships.

**Tech Stack:** Python, FastAPI, Pillow (PIL) for image processing, Google Generative AI SDK (Gemini 1.5 Pro).

---

### Task 1: Image Preprocessor (Smart Cropping)

**Goal:** Create a utility that takes a full page image and a list of equipment coordinates, and returns cropped images centered on each piece of equipment with sufficient context (1000x1000px).

**Files:**
- Create: `backend/app/services/vision/image_preprocessor.py`
- Test: `backend/tests/vision/test_image_preprocessor.py`

**Step 1: Write the failing test**

Create `backend/tests/vision/test_image_preprocessor.py`:
```python
import pytest
from PIL import Image
from app.services.vision.image_preprocessor import ImagePreprocessor

def test_crop_centered_on_equipment():
    # Create a dummy 2000x2000 image
    img = Image.new('RGB', (2000, 2000), color='white')
    
    # Define equipment at (500, 500)
    bbox = {"x_min": 450, "y_min": 450, "x_max": 550, "y_max": 550}
    
    preprocessor = ImagePreprocessor()
    crop = preprocessor.create_centered_crop(img, bbox, crop_size=1000)
    
    # Expected: crop should be 1000x1000
    assert crop.size == (1000, 1000)
    # The center of the equipment (500,500) should be at center of crop (500,500)
    # So crop should be from (0, 0) to (1000, 1000)
    
def test_crop_at_boundary():
    # Equipment at edge (100, 100)
    img = Image.new('RGB', (2000, 2000), color='white')
    bbox = {"x_min": 50, "y_min": 50, "x_max": 150, "y_max": 150}
    
    preprocessor = ImagePreprocessor()
    crop = preprocessor.create_centered_crop(img, bbox, crop_size=1000)
    
    # Should handle boundary by shifting crop or padding? 
    # For simplicity, let's shift to stay within bounds: (0,0) to (1000,1000)
    assert crop.size == (1000, 1000)
```

**Step 2: Run test to verify it fails**

Run: `export PYTHONPATH=$PYTHONPATH:$(pwd)/backend && pytest backend/tests/vision/test_image_preprocessor.py`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write implementation**

Create `backend/app/services/vision/image_preprocessor.py`:
```python
from PIL import Image
from typing import Dict, Tuple

class ImagePreprocessor:
    def create_centered_crop(self, image: Image.Image, bbox: Dict[str, float], crop_size: int = 1000) -> Image.Image:
        """
        Create a square crop centered on the bounding box.
        Ensures crop stays within image boundaries.
        """
        img_w, img_h = image.size
        
        # Calculate center of bbox
        center_x = (bbox["x_min"] + bbox["x_max"]) / 2
        center_y = (bbox["y_min"] + bbox["y_max"]) / 2
        
        # Calculate crop coordinates
        half_size = crop_size / 2
        left = center_x - half_size
        top = center_y - half_size
        right = center_x + half_size
        bottom = center_y + half_size
        
        # Adjust to stay within bounds
        if left < 0:
            right += -left  # Shift right
            left = 0
        if top < 0:
            bottom += -top  # Shift down
            top = 0
        if right > img_w:
            left -= (right - img_w) # Shift left
            right = img_w
        if bottom > img_h:
            top -= (bottom - img_h) # Shift up
            bottom = img_h
            
        # Ensure we don't go out of bounds after shifting (if image is smaller than crop)
        left = max(0, left)
        top = max(0, top)
        right = min(img_w, right)
        bottom = min(img_h, bottom)
        
        return image.crop((left, top, right, bottom))
```

**Step 4: Run test to verify it passes**

Run: `export PYTHONPATH=$PYTHONPATH:$(pwd)/backend && pytest backend/tests/vision/test_image_preprocessor.py`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/vision/image_preprocessor.py backend/tests/vision/test_image_preprocessor.py
git commit -m "feat: add image preprocessor for smart cropping"
```

---

### Task 2: Gemini Vision Client

**Goal:** Implement the client that sends images to Gemini 1.5 Pro with a specific prompt to trace lines.

**Files:**
- Create: `backend/app/services/vision/gemini_client.py`
- Test: `backend/tests/vision/test_gemini_client.py`

**Step 1: Write the failing test**

Create `backend/tests/vision/test_gemini_client.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.vision.gemini_client import GeminiVisionClient

def test_analyze_crop():
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"relationships": [{"target": "P-101", "type": "feeds"}]}'
    mock_model.generate_content.return_value = mock_response
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model):
        client = GeminiVisionClient()
        # Mock PIL image
        img = MagicMock()
        
        result = client.analyze_crop(img, focus_tag="MCC-1")
        
        assert result["relationships"][0]["target"] == "P-101"
        assert "MCC-1" in mock_model.generate_content.call_args[0][0][0] # Prompt check
```

**Step 2: Run test to verify it fails**

Run: `export PYTHONPATH=$PYTHONPATH:$(pwd)/backend && pytest backend/tests/vision/test_gemini_client.py`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/app/services/vision/gemini_client.py`:
```python
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
```

**Step 4: Run test to verify it passes**

Run: `export PYTHONPATH=$PYTHONPATH:$(pwd)/backend && pytest backend/tests/vision/test_gemini_client.py`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/vision/gemini_client.py backend/tests/vision/test_gemini_client.py
git commit -m "feat: add gemini vision client"
```

---

### Task 3: Vision Extraction Service (Orchestrator)

**Goal:** Coordinate the workflow: verify equipment presence -> crop -> analyze -> merge results.

**Files:**
- Create: `backend/app/services/vision_extraction_service.py`
- Test: `backend/tests/vision/test_vision_extraction_service.py`

**Step 1: Write the failing test**

Create `backend/tests/vision/test_vision_extraction_service.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.vision_extraction_service import VisionExtractionService

def test_process_page():
    mock_preprocessor = MagicMock()
    mock_client = MagicMock()
    
    # Setup mocks
    mock_crop = MagicMock()
    mock_preprocessor.create_centered_crop.return_value = mock_crop
    
    mock_client.analyze_crop.return_value = {
        "relationships": [{"target": "P-101", "type": "feeds"}]
    }
    
    service = VisionExtractionService()
    service.preprocessor = mock_preprocessor
    service.client = mock_client
    
    # Mock page image and equipment list
    page_image = MagicMock()
    equipment_list = [
        {"tag": "MCC-1", "bbox": {"x_min": 100, "y_min": 100, "x_max": 200, "y_max": 200}}
    ]
    
    results = service.process_page(page_image, equipment_list)
    
    assert len(results) == 1
    assert results[0]["source"] == "MCC-1"
    assert results[0]["target"] == "P-101"
    assert results[0]["method"] == "vision"
```

**Step 2: Run test to verify it fails**

Run: `export PYTHONPATH=$PYTHONPATH:$(pwd)/backend && pytest backend/tests/vision/test_vision_extraction_service.py`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/app/services/vision_extraction_service.py`:
```python
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
```

**Step 4: Run test to verify it passes**

Run: `export PYTHONPATH=$PYTHONPATH:$(pwd)/backend && pytest backend/tests/vision/test_vision_extraction_service.py`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/vision_extraction_service.py backend/tests/vision/test_vision_extraction_service.py
git commit -m "feat: add vision extraction service orchestrator"
```

