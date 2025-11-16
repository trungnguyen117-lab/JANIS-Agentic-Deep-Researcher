"""Debug script to check if token usage is being preserved in LangGraph messages."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
_project_root = Path(__file__).parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

load_dotenv()

import sys
from pathlib import Path

# Add parent directory to path
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from langchain_core.messages import HumanMessage, AIMessage
from backend.config import get_model

def main():
    """Test if token usage is in LLM responses."""
    model = get_model("gpt-4o-mini")
    
    print("Making LLM call...")
    messages = [HumanMessage(content="Say hello in one sentence.")]
    response = model.invoke(messages)
    
    print(f"\nResponse type: {type(response)}")
    print(f"Response ID: {response.id}")
    
    # Check usage_metadata
    print("\n=== usage_metadata ===")
    if hasattr(response, 'usage_metadata'):
        print(f"Has usage_metadata: True")
        print(f"usage_metadata: {response.usage_metadata}")
        if response.usage_metadata:
            print(f"Keys: {list(response.usage_metadata.keys()) if isinstance(response.usage_metadata, dict) else 'Not a dict'}")
    else:
        print("Has usage_metadata: False")
    
    # Check response_metadata
    print("\n=== response_metadata ===")
    if hasattr(response, 'response_metadata'):
        print(f"Has response_metadata: True")
        print(f"response_metadata: {response.response_metadata}")
        if response.response_metadata and 'token_usage' in response.response_metadata:
            print(f"token_usage: {response.response_metadata['token_usage']}")
    else:
        print("Has response_metadata: False")
    
    # Check as dict
    print("\n=== As dict ===")
    try:
        msg_dict = response.dict() if hasattr(response, 'dict') else None
        if msg_dict:
            print(f"Has usage_metadata in dict: {'usage_metadata' in msg_dict}")
            if 'usage_metadata' in msg_dict:
                print(f"usage_metadata: {msg_dict['usage_metadata']}")
            if 'response_metadata' in msg_dict:
                print(f"response_metadata: {msg_dict['response_metadata']}")
    except Exception as e:
        print(f"Error converting to dict: {e}")

if __name__ == "__main__":
    main()

