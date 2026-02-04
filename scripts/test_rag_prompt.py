import sys
import os
from unittest.mock import MagicMock

# Mock modules to avoid loading heavy or missing dependencies
sys.modules["app.services.search_service"] = MagicMock()
sys.modules["app.services.graph_service"] = MagicMock()
sys.modules["app.models.schemas"] = MagicMock()
# Mock search_service instance specifically if needed
sys.modules["backend.app.services.search_service"] = MagicMock()
sys.modules["backend.app.services.graph_service"] = MagicMock()
sys.modules["backend.app.models.schemas"] = MagicMock()

# Also mock paddleocr and fitz just in case
sys.modules["paddleocr"] = MagicMock()
sys.modules["fitz"] = MagicMock()
sys.modules["pdf2image"] = MagicMock()

sys.path.append(os.getcwd())
from backend.app.services.rag_service import rag_service

def test_prompt_generation():
    system_prompt = rag_service._get_system_prompt()
    print("=== SYSTEM PROMPT ===")
    print(system_prompt)
    
    # We want these rules to be present.
    # Currently they are NOT, so this should fail.
    assert "FORMATTING RULES (STRICT)" in system_prompt, "System prompt missing strict formatting rules"

if __name__ == "__main__":
    test_prompt_generation()
