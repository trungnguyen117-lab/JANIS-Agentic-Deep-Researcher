"""Main entry point for the research agent system."""

from dotenv import load_dotenv

# Import from local deepagents module
import sys
from pathlib import Path

# Add project root to path so we can import backend.deepagents
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import using absolute path from project root
from backend.deepagents import create_deep_agent

# Import other modules using absolute imports from backend
from backend.config import get_model
from backend.tools import arxiv_search
from backend.prompts import orchestrator_instructions
from backend.agents import create_sub_agents

# Load environment variables
load_dotenv()

# Initialize model
model = get_model()

# Create sub-agents
sub_agents = create_sub_agents()

# Create the main orchestrator agent
agent = create_deep_agent(
    model=model,
    tools=[arxiv_search],  # Orchestrator may need basic tools for coordination
    system_prompt=orchestrator_instructions,
    subagents=sub_agents
)
