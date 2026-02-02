import pytest
from unittest.mock import MagicMock, patch, ANY
# We need to mock imports that might fail in this environment
import sys
from unittest.mock import MagicMock

# Create mocks for services if they can't be imported
sys.modules['app.services.ocr_service'] = MagicMock()
sys.modules['app.services.extraction_service'] = MagicMock()
sys.modules['app.services.embedding_service'] = MagicMock()
sys.modules['app.services.ai_analysis_service'] = MagicMock()
# sys.modules['app.services.vision_extraction_service'] = MagicMock() # Don't mock this if we want to test import
# But we are mocking the usage

from app.services.document_processor import DocumentProcessor

def test_vision_integration():
    with patch('app.services.document_processor.ocr_service') as mock_ocr, \
         patch('app.services.document_processor.ai_analysis_service') as mock_ai, \
         patch('app.services.document_processor.embedding_service') as mock_embed, \
         patch('app.services.document_processor.extraction_service') as mock_extract, \
         patch('app.services.document_processor.vision_extraction_service') as mock_vision, \
         patch('app.services.document_processor.Image.open') as mock_img_open:
         
        # Setup returns
        mock_ocr.process_document.return_value = [{
            "page_number": 1,
            "ocr_text": "MCC-1 feeds P-101", 
            "image_path": "dummy.jpg",
            "elements": []
        }]
        
        mock_ai.analyze_page.return_value = {"equipment": [], "analysis": ""}
        
        # Mock extracted equipment
        eq_mock = MagicMock()
        eq_mock.tag = "MCC-1"
        eq_mock.bbox = {"x_min": 10, "y_min": 10, "x_max": 100, "y_max": 100}
        mock_extract.extract_equipment_tags.return_value = [eq_mock]
        
        mock_extract.extract_relationships.return_value = []
        
        # Vision returns a relationship
        mock_vision.process_page.return_value = [{
            "source": "MCC-1", "target": "P-101", "type": "feeds", "confidence": "high"
        }]
        
        # Run processor
        processor = DocumentProcessor()
        db = MagicMock()
        doc = MagicMock()
        doc.id = 1
        doc.file_size = 1024 * 1024 * 10 # 10MB
        doc.original_filename = "test.pdf"
        db.query().filter().first.return_value = doc
        
        # Call
        processor.process_document(db, 1)
        
        # Verify vision was called
        mock_vision.process_page.assert_called_once()
        
        # Verify Image.open was called
        mock_img_open.assert_called_with("dummy.jpg")
