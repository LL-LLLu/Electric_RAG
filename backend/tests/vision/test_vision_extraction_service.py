import pytest
from unittest.mock import MagicMock, patch
# We need to make sure these imports work, even if we mock them
try:
    from app.services.vision_extraction_service import VisionExtractionService
except ImportError:
    VisionExtractionService = None

def test_process_page():
    if VisionExtractionService is None:
        pytest.fail("VisionExtractionService module not found")

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
