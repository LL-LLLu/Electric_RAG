import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure the app module can be found
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

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
        # Verify prompt contains the focus tag
        assert "MCC-1" in mock_model.generate_content.call_args[0][0][0]
