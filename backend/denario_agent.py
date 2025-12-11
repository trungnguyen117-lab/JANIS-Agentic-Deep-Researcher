"""Denario agent wrapper for LangGraph integration."""

from typing import Any, Dict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.state import CompiledStateGraph

from .denario_workflow import create_denario_workflow, DenarioWorkflowState


def create_denario_agent(model: BaseChatModel = None) -> CompiledStateGraph:
    """Create Denario agent compatible with LangGraph interface.
    
    This function creates a Denario workflow graph that can be used as a LangGraph agent.
    The workflow follows a fixed sequence:
    1. Initialize → Extract data description from user message
    2. Generate Idea → Create research idea
    3. Generate Method → Create methodology
    4. Generate Results → Run experiments
    5. Generate Paper → Create LaTeX paper
    
    Args:
        model: Language model (for compatibility, not used directly in Denario workflow)
    
    Returns:
        Compiled LangGraph that can be used as agent
    """
    return create_denario_workflow()

