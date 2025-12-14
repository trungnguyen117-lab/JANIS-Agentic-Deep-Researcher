"""LangGraph agent creation - simple outline agent."""

from typing import Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig
import logging

logger = logging.getLogger(__name__)

from .config import get_model
from .prompts import outline_agent_prompt
from .tools import create_outline_tool, validate_json, generate_paper_from_outline


def create_agent(model_name: str | None = None):
    """Create the outline agent using LangGraph.
    
    This is a simple agent that creates and fixes paper outlines.
    Denario handles the rest of the paper generation.
    
    Args:
        model_name: Name of the model to use. If None, uses default from environment.
    
    Returns:
        The configured LangGraph agent
    """
    import os
    
    # Get model name from parameter or environment
    if model_name is None:
        model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    
    # Initialize model
    model = get_model(model_name)
    
    # Bind tools to model (outline creation + paper generation)
    tools = [create_outline_tool, validate_json, generate_paper_from_outline]
    model_with_tools = model.bind_tools(tools)
    
    # Define state
    from typing_extensions import TypedDict
    
    class AgentState(TypedDict, total=False):
        messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
        files: dict[str, str]  # Files dictionary for frontend to read
    
    # Create graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    def call_model(state: AgentState, config: RunnableConfig):
        """Call the model with current messages."""
        messages = state["messages"]
        # Add system prompt if this is the first message
        if not messages:
            messages = [SystemMessage(content=outline_agent_prompt)]
        elif not any(isinstance(msg, SystemMessage) for msg in messages):
            # Prepend system message if not present
            messages = [SystemMessage(content=outline_agent_prompt)] + list(messages)
        response = model_with_tools.invoke(messages, config=config)
        return {"messages": [response]}
    
    graph.add_node("agent", call_model)
    
    # Custom tools node that also syncs outline JSON and paper files to state
    def tools_node(state: AgentState, config: RunnableConfig):
        """Execute tools and extract outline JSON and paper files to state."""
        import json
        
        # Store config in context variables so tools can access it
        # This is needed because StructuredTool.from_function doesn't pass config automatically
        try:
            from src.research_agent.tools.outline_creator import _config_var as outline_config_var
            outline_config_var.set(config)
        except Exception as e:
            logger.warning(f"Could not set config in outline_creator context var: {e}")
        
        try:
            from src.research_agent.tools.denario_paper_generator import _config_var as denario_config_var
            denario_config_var.set(config)
        except Exception as e:
            logger.warning(f"Could not set config in denario_paper_generator context var: {e}")
        
        # Extract thread_id from config for debugging
        thread_id = None
        if config:
            if hasattr(config, 'configurable'):
                configurable = config.configurable
                if isinstance(configurable, dict):
                    thread_id = configurable.get('thread_id')
                elif hasattr(configurable, 'get'):
                    thread_id = configurable.get('thread_id')
        
        if thread_id:
            logger.info(f"🔍 Tools node: thread_id={thread_id}")
        else:
            logger.warning(f"⚠️ Tools node: No thread_id found in config. Config type: {type(config)}")
            if config:
                logger.debug(f"Config attributes: {dir(config)}")
                if hasattr(config, 'configurable'):
                    logger.debug(f"Config.configurable: {config.configurable}, type: {type(config.configurable)}")
        
        # Execute tools - ToolNode should pass config via execution context
        # The config is also stored in contextvars for tools to access
        tool_node = ToolNode(tools)
        result = tool_node.invoke(state, config)
        
        # After tool execution, extract data from tool response and add to state
        messages = result.get("messages", [])
        outline_json = None
        paper_files = {}
        
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = str(msg.content) if hasattr(msg, 'content') else ""
                
                # Check if this is the create_outline tool response (works for both initial creation and updates)
                if 'outline created successfully' in content.lower() and 'OUTLINE_JSON_START' in content:
                    # Extract JSON from between markers
                    try:
                        start_marker = 'OUTLINE_JSON_START\n'
                        end_marker = '\nOUTLINE_JSON_END'
                        start_idx = content.find(start_marker)
                        end_idx = content.find(end_marker)
                        if start_idx != -1 and end_idx != -1:
                            json_str = content[start_idx + len(start_marker):end_idx].strip()
                            outline_json = json_str
                            logger.info(f"✅ Extracted outline JSON from tool response ({len(json_str)} chars)")
                    except Exception as e:
                        logger.warning(f"Failed to extract outline JSON from tool response: {e}")
                
                # Check if this is the generate_paper_from_outline tool response
                if 'paper' in content.lower() and 'generated successfully' in content.lower():
                    # Try to extract paper files from markers first
                    if 'PAPER_FILES_START' in content:
                        try:
                            start_marker = 'PAPER_FILES_START\n'
                            end_marker = '\nPAPER_FILES_END'
                            start_idx = content.find(start_marker)
                            end_idx = content.find(end_marker)
                            if start_idx != -1 and end_idx != -1:
                                files_str = content[start_idx + len(start_marker):end_idx].strip()
                                # Parse file entries (format: path:content)
                                # Content can span multiple lines, so we need to handle that
                                lines = files_str.split('\n')
                                current_path = None
                                current_content = []
                                
                                for line in lines:
                                    # Check if this line starts a new file entry (has ':' and looks like a path)
                                    # A file path typically doesn't start with whitespace and has ':' followed by content
                                    if ':' in line and (current_path is None or (line.strip() and not line.startswith(' ') and ':' in line and line.split(':', 1)[0].strip().endswith(('.tex', '.pdf', '.json', '.md')))):
                                        # Save previous file if we were processing one
                                        if current_path and current_content:
                                            paper_files[current_path] = '\n'.join(current_content)
                                        
                                        # Start new file entry - split only on first ':' to get path
                                        parts = line.split(':', 1)
                                        if len(parts) == 2:
                                            current_path = parts[0].strip()
                                            current_content = [parts[1]] if parts[1].strip() else []  # Start with content after first ':'
                                    elif current_path is not None:
                                        # This is a continuation of the current file's content
                                        current_content.append(line)
                                
                                # Save the last file if we were processing one
                                if current_path and current_content:
                                    # Join all content lines, preserving newlines
                                    paper_files[current_path] = '\n'.join(current_content)
                                
                                logger.info(f"✅ Extracted {len(paper_files)} paper files from tool response: {list(paper_files.keys())}")
                        except Exception as e:
                            logger.warning(f"Failed to extract paper files from tool response: {e}")
                    
                    # Also read files directly from disk (more reliable than parsing from message)
                    # Extract thread_id to find the correct directory
                    thread_id = None
                    if config and hasattr(config, 'configurable'):
                        configurable = config.configurable
                        if isinstance(configurable, dict):
                            thread_id = configurable.get('thread_id')
                    
                    if thread_id:
                        # Read all LaTeX files from thread's paper directory
                        try:
                            from pathlib import Path
                            project_root = Path(__file__).parent.parent.parent.parent.parent
                            paper_dir = project_root / "project" / "threads" / str(thread_id) / "paper"
                            
                            if paper_dir.exists():
                                # Find all .tex files in the paper directory
                                latex_files = list(paper_dir.glob("*.tex"))
                                
                                for latex_file in sorted(latex_files):
                                    try:
                                        # Get relative path for state (e.g., "paper/paper_v4_final.tex")
                                        relative_path = latex_file.relative_to(project_root / "project" / "threads" / str(thread_id))
                                        
                                        # Read file content
                                        with latex_file.open("r", encoding="utf-8") as f:
                                            latex_content = f.read()
                                        
                                        # Add or update in paper_files (overwrite if already exists from message parsing)
                                        paper_files[str(relative_path)] = latex_content
                                        logger.info(f"✅ Read LaTeX file from disk: {relative_path} ({len(latex_content)} chars)")
                                    except Exception as e:
                                        logger.warning(f"Failed to read LaTeX file {latex_file}: {e}")
                                
                                # Also check if we need to read files that were marked as <READ_FROM_DISK>
                                if 'PAPER_FILES_START' in content:
                                    start_marker = 'PAPER_FILES_START\n'
                                    end_marker = '\nPAPER_FILES_END'
                                    start_idx = content.find(start_marker)
                                    end_idx = content.find(end_marker)
                                    if start_idx != -1 and end_idx != -1:
                                        files_str = content[start_idx + len(start_marker):end_idx].strip()
                                        for line in files_str.split('\n'):
                                            if ':<READ_FROM_DISK>' in line:
                                                file_path = line.split(':<READ_FROM_DISK>')[0].strip()
                                                # Read from disk
                                                full_path = paper_dir / Path(file_path).name
                                                if full_path.exists():
                                                    try:
                                                        with full_path.open("r", encoding="utf-8") as f:
                                                            file_content = f.read()
                                                        paper_files[file_path] = file_content
                                                        logger.info(f"✅ Read file from disk (marked): {file_path} ({len(file_content)} chars)")
                                                    except Exception as e:
                                                        logger.warning(f"Failed to read file {full_path}: {e}")
                        except Exception as e:
                            logger.warning(f"Failed to read LaTeX files from disk: {e}")
        
        # Update files in state
        files = state.get("files", {})
        if outline_json:
            files["project/plan_outline.json"] = outline_json
            logger.info(f"✅ Added outline to state: project/plan_outline.json")
        
        if paper_files:
            files.update(paper_files)
            logger.info(f"✅ Added {len(paper_files)} paper files to state: {list(paper_files.keys())}")
        
        if outline_json or paper_files:
            result["files"] = files
        
        return result
    
    graph.add_node("tools", tools_node)
    
    # Add edges
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        lambda x: "tools" if x["messages"][-1].tool_calls else END,
    )
    graph.add_edge("tools", "agent")
    
    # Compile graph (LangGraph API handles persistence automatically)
    agent = graph.compile()
    
    return agent

