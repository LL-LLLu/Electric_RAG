# scripts/test_multi_agent_prompt.py
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
# from backend.app.services.multi_agent_search_service import multi_agent_search_service

def test_prompt_content():
    # We will modify the code to verify the string exists in the file content 
    # since we can't easily unit test the private method without refactoring.
    with open("backend/app/services/multi_agent_search_service.py", "r") as f:
        content = f.read()
    
    assert "FORMATTING RULES" in content, "FORMATTING RULES not found in MultiAgentSearchService code"

if __name__ == "__main__":
    try:
        test_prompt_content()
        print("Test passed!")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
