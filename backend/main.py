"""Main entry point for the research agent system."""

from dotenv import load_dotenv
import os

import sys
from pathlib import Path

# Add project root to path so we can import backend modules
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Add backend/src to path for research-agent imports
_backend_src = Path(__file__).parent / "src"
if str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

# Import agent creation from research_agent
from src.research_agent.graph import create_agent

# Load environment variables
load_dotenv()

# Initialize token tracking (must be done before importing LangChain models)
from src.research_agent.config.token_tracking_setup import setup_token_tracking
setup_token_tracking()

# Create default agent with model from environment
# This is used when LangGraph CLI loads the agent
agent = create_agent()
