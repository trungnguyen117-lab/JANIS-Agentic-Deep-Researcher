"""Main entry point for the research agent system."""

from dotenv import load_dotenv
import os

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
from backend.config import get_model, AVAILABLE_MODELS
from backend.config.langfuse import get_langfuse_handler
from backend.config.opentelemetry_tracker import setup_opentelemetry_tracking
from backend.tools import arxiv_search
from backend.prompts import orchestrator_instructions, new_prompt
from backend.agents import create_sub_agents

# Load environment variables
load_dotenv()

# Initialize token tracking (must be done before importing LangChain models)
# Uses TOKEN_TRACKING_LIBRARY environment variable to choose between:
# - "openlit" (default): OpenLIT automatic instrumentation
# - "opentelemetry": OpenTelemetry direct instrumentation
# - "langfuse": Langfuse API queries (requires LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
from backend.config.token_tracking_setup import setup_token_tracking
setup_token_tracking()


def create_agent(model_name: str | None = None):
    """Create the main orchestrator agent with specified model.
    
    Args:
        model_name: Name of the model to use. If None, uses default from environment.
    
    Returns:
        The configured deep agent
    """
    # Get model name from parameter or environment
    if model_name is None:
        model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    
    # Initialize model
    model = get_model(model_name)
    
    # Create sub-agents
    sub_agents = create_sub_agents()
    
    # Get Langfuse callback handler if configured (optional)
    langfuse_handler = get_langfuse_handler()
    
    # Collect callbacks (OpenLIT tracks token usage automatically via spans)
    callbacks = []
    if langfuse_handler:
        callbacks.append(langfuse_handler)
    
    # Create the main orchestrator agent
    agent = create_deep_agent(
        model=model,
        tools=[arxiv_search],  # Orchestrator tools: basic coordination (aggregate_document is provided by FilesystemMiddleware)
        system_prompt=new_prompt,
        subagents=sub_agents
    )
    
    # Add callbacks to default config (if any)
    if callbacks:
        agent = agent.with_config({"callbacks": callbacks})
    
    return agent


# Create default agent with model from environment
# This is used when LangGraph CLI loads the agent
agent = create_agent()
