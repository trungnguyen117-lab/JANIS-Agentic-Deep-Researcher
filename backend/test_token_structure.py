#!/usr/bin/env python3
"""Test script to inspect actual LLM response structure and token usage metadata."""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load environment variables from project root
env_path = _project_root / ".env"
load_dotenv(env_path)

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from backend.config import get_model

def inspect_message_structure(message):
    """Inspect and print the full structure of an AIMessage."""
    print("=" * 80)
    print("MESSAGE STRUCTURE INSPECTION")
    print("=" * 80)
    
    # Print message type
    print(f"\nMessage Type: {type(message).__name__}")
    print(f"Message ID: {getattr(message, 'id', 'N/A')}")
    
    # Print all attributes
    print("\n--- All Attributes ---")
    attrs = dir(message)
    for attr in attrs:
        if not attr.startswith('_'):
            try:
                value = getattr(message, attr)
                if not callable(value):
                    print(f"  {attr}: {type(value).__name__}")
            except:
                pass
    
    # Check for usage_metadata
    print("\n--- usage_metadata ---")
    if hasattr(message, 'usage_metadata'):
        usage = message.usage_metadata
        print(f"  Type: {type(usage)}")
        if usage:
            print(f"  Value: {json.dumps(usage, indent=2, default=str)}")
            print(f"  Keys: {list(usage.keys()) if isinstance(usage, dict) else 'Not a dict'}")
        else:
            print("  Value: None or empty")
    else:
        print("  Not found")
    
    # Check for response_metadata
    print("\n--- response_metadata ---")
    if hasattr(message, 'response_metadata'):
        metadata = message.response_metadata
        print(f"  Type: {type(metadata)}")
        if metadata:
            print(f"  Value: {json.dumps(metadata, indent=2, default=str)}")
            print(f"  Keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'Not a dict'}")
            
            # Check for usage_metadata inside response_metadata
            if isinstance(metadata, dict) and 'usage_metadata' in metadata:
                print("\n  --- response_metadata.usage_metadata ---")
                usage_meta = metadata['usage_metadata']
                print(f"    Value: {json.dumps(usage_meta, indent=2, default=str)}")
                print(f"    Keys: {list(usage_meta.keys()) if isinstance(usage_meta, dict) else 'Not a dict'}")
            
            # Check for token_usage inside response_metadata
            if isinstance(metadata, dict) and 'token_usage' in metadata:
                print("\n  --- response_metadata.token_usage ---")
                token_usage = metadata['token_usage']
                print(f"    Value: {json.dumps(token_usage, indent=2, default=str)}")
                print(f"    Keys: {list(token_usage.keys()) if isinstance(token_usage, dict) else 'Not a dict'}")
        else:
            print("  Value: None or empty")
    else:
        print("  Not found")
    
    # Check for usage attribute
    print("\n--- usage (direct attribute) ---")
    if hasattr(message, 'usage'):
        usage = message.usage
        print(f"  Type: {type(usage)}")
        if usage:
            print(f"  Value: {json.dumps(usage, indent=2, default=str)}")
            print(f"  Keys: {list(usage.keys()) if isinstance(usage, dict) else 'Not a dict'}")
        else:
            print("  Value: None or empty")
    else:
        print("  Not found")
    
    # Try to access as dict
    print("\n--- As Dictionary (if possible) ---")
    try:
        msg_dict = message.dict() if hasattr(message, 'dict') else None
        if msg_dict:
            print("  Message as dict keys:", list(msg_dict.keys()))
            if 'usage_metadata' in msg_dict:
                print(f"  usage_metadata in dict: {json.dumps(msg_dict['usage_metadata'], indent=2, default=str)}")
            if 'response_metadata' in msg_dict:
                print(f"  response_metadata in dict: {json.dumps(msg_dict['response_metadata'], indent=2, default=str)}")
    except Exception as e:
        print(f"  Error converting to dict: {e}")
    
    # Print full message representation
    print("\n--- Full Message Representation ---")
    try:
        print(json.dumps(message.dict() if hasattr(message, 'dict') else str(message), indent=2, default=str))
    except Exception as e:
        print(f"  Error: {e}")
        print(f"  String representation: {str(message)[:500]}")

def main():
    """Test LLM call and inspect response structure."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment")
        sys.exit(1)
    
    # Use a reasoning model for testing
    model_name = "gemini-2.5-pro-thinking"
    print(f"Testing with model: {model_name}")
    print(f"API Key present: {'Yes' if api_key else 'No'}")
    print(f"API Base URL: {os.getenv('API_BASE_URL', 'Not set')}")
    
    # Use OpenAI-compatible interface (same as backend)
    # The backend uses init_chat_model with provider prefix, but for testing
    # we'll use ChatOpenAI directly with the base_url to match backend setup
    base_url = os.getenv("API_BASE_URL", "http://api.pinkyne.com/v1/")
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )
    print(f"Using OpenAI-compatible interface with base_url: {base_url}")
    
    # Make a complex call that will trigger reasoning
    print("\n" + "=" * 80)
    print("MAKING LLM CALL WITH COMPLEX QUESTION...")
    print("=" * 80)
    
    try:
        messages = [HumanMessage(content="""Solve this step by step: 
        A company has 3 departments. Department A has 25 employees, Department B has 30% more employees than Department A, 
        and Department C has 2/3 the number of employees as Department B. 
        If each employee costs $50,000 per year, what is the total annual cost for all departments?
        Show your reasoning.""")]
        response = llm.invoke(messages)
        
        print("\nCall successful!")
        print(f"Response type: {type(response).__name__}")
        print(f"Response content: {response.content[:100]}...")
        
        # Inspect the response structure
        inspect_message_structure(response)
        
        # Also check if there's additional info in the response
        print("\n" + "=" * 80)
        print("ADDITIONAL CHECKS")
        print("=" * 80)
        
        # Check for any other attributes that might contain token info
        for attr in ['token_usage', 'usage', 'tokens', 'prompt_tokens', 'completion_tokens']:
            if hasattr(response, attr):
                value = getattr(response, attr)
                print(f"\n{attr}: {value} (type: {type(value).__name__})")
        
    except Exception as e:
        print(f"\nERROR during LLM call: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

