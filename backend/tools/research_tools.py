"""Research delegation tools for supervisor-researcher architecture.

Note: These are placeholder tools. The actual delegation will be handled by the orchestrator
when it sees these tool calls from the supervisor agent. The orchestrator will then spawn
individual researcher agents to handle each research task.
"""

from langchain_core.tools import tool


@tool
def conduct_research(research_topic: str) -> str:
    """Delegate a research task to an individual researcher.
    
    Each call to this tool signals that a research task should be delegated to a dedicated
    researcher agent. The orchestrator will spawn a researcher agent to handle this topic.
    
    The researcher will:
    1. Decompose the research topic into sub-queries
    2. Search arXiv iteratively using arxiv_search
    3. Use think_tool for reflection between searches
    4. Compress findings into a structured summary
    5. Save findings to research_findings_[topic].md
    
    IMPORTANT: 
    - Provide detailed, standalone instructions in research_topic
    - Be very specific and clear - avoid acronyms or abbreviations
    - Each researcher works independently - they can't see other researchers' work
    - The research_topic should be at least a paragraph describing what to research
    
    Args:
        research_topic: The specific topic to research. Should be a single, focused topic 
                       described in detail (at least a paragraph). Be very specific and clear.
    
    Returns:
        Confirmation message that the research task has been delegated.
    """
    # This is a signal tool - the actual work is done by the orchestrator
    # which spawns researcher agents when it sees this tool call
    return f"Research task delegated: {research_topic}. A dedicated researcher will conduct research on this topic."


@tool
def research_complete() -> str:
    """Signal that research is complete.
    
    Call this when you are satisfied with the research findings and have gathered
    sufficient information to answer the research question comprehensively.
    
    Returns:
        Confirmation that research phase is complete.
    """
    return "Research phase marked as complete. Proceeding to results interpretation phase."


# Alias for compatibility
ConductResearch = conduct_research
ResearchComplete = research_complete

