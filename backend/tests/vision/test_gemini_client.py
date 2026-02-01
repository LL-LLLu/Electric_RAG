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

def test_markdown_json_response():
    mock_model = MagicMock()
    mock_response = MagicMock()
    # Gemini often returns markdown code blocks
    mock_response.text = '```json\n{"relationships": [{"target": "P-102", "type": "controls"}]}\n```'
    mock_model.generate_content.return_value = mock_response
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model):
        client = GeminiVisionClient()
        img = MagicMock()
        result = client.analyze_crop(img, "TAG")
        
        assert result["relationships"][0]["target"] == "P-102"

def test_markdown_with_prose_and_braces():
    mock_model = MagicMock()
    mock_response = MagicMock()
    # Case where simple find('{') might fail if prose contains braces
    mock_response.text = """
    Here is the analysis {context}:
    ```json
    {
        "relationships": [
            {
                "target": "V-101", 
                "type": "feeds"
            }
        ]
    }
    ```
    Hope this helps! }
    """
    mock_model.generate_content.return_value = mock_response
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model):
        client = GeminiVisionClient()
        img = MagicMock()
        result = client.analyze_crop(img, "TAG")
        
        # This currently fails or returns error because it captures outer braces
        assert result["relationships"][0]["target"] == "V-101"

def test_api_failure():
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("API Error")
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model):
        client = GeminiVisionClient()
        img = MagicMock()
        
        with patch('app.services.vision.gemini_client.logger') as mock_logger:
            result = client.analyze_crop(img, "TAG")
            
            assert result == {}
            mock_logger.error.assert_called_once()
            assert "Gemini vision analysis failed" in mock_logger.error.call_args[0][0]

def test_invalid_json():
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "I'm sorry, I cannot identify the relationships."
    mock_model.generate_content.return_value = mock_response
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model):
        client = GeminiVisionClient()
        img = MagicMock()
        result = client.analyze_crop(img, "TAG")
        
        assert result == {}

def test_missing_api_key():
    with patch.dict(os.environ, {}, clear=True):
        with patch('app.services.vision.gemini_client.logger') as mock_logger:
            client = GeminiVisionClient()
            assert client.model is None
            mock_logger.warning.assert_called_with("GEMINI_API_KEY not set")
            
            # Should safely return empty dict
            img = MagicMock()
            result = client.analyze_crop(img, "TAG")
            assert result == {}
