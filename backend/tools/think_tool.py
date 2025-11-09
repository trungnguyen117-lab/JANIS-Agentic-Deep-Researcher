"""Think tool for strategic reflection during research."""

from langchain_core.tools import tool


@tool
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection and planning during research.
    
    Use this tool to:
    - Plan your research approach before starting
    - Reflect on search results and decide next steps
    - Assess progress and determine if more research is needed
    - Think through complex problems
    
    IMPORTANT: Do NOT call this tool in parallel with other tools. 
    Use it separately for reflection, then use other tools based on your reflection.
    
    Args:
        reflection: Your thoughts, analysis, or strategic planning. 
                   This should be a detailed reflection on your current situation,
                   what you've learned, what you need to do next, etc.
    
    Returns:
        Confirmation message that your reflection has been recorded.
    """
    # The reflection is recorded in the conversation history
    # This tool primarily serves as a structured way for the agent to think
    return f"Reflection recorded: {reflection}"

