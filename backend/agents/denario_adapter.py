"""Adapter to make Denario workflow compatible with sub-agent system."""

import os
from typing import Any, Iterator, AsyncIterator
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langgraph.graph.state import CompiledStateGraph

from ..denario_workflow import create_denario_workflow, DenarioWorkflowState


class DenarioSubAgentAdapter(Runnable):
    """Adapter that wraps Denario workflow to work as a sub-agent.
    
    This adapter converts the sub-agent call format (HumanMessage with task description)
    into the Denario workflow state format, runs the workflow, and returns the result.
    """
    
    def __init__(self, workflow: CompiledStateGraph | None = None):
        """Initialize the adapter.
        
        Args:
            workflow: The Denario workflow graph. If None, creates a new one.
        """
        self.workflow = workflow or create_denario_workflow()
    
    def invoke(self, input: dict[str, Any], config: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        """Invoke the Denario workflow with sub-agent input format.
        
        Args:
            input: Input from sub-agent system. Expected format:
                - messages: list of BaseMessage (should contain HumanMessage with task description)
            config: Optional configuration for the workflow
            **kwargs: Additional keyword arguments (ignored, for compatibility)
        
        Returns:
            dict with 'messages' key containing the workflow result
        """
        # Extract messages from input
        messages = input.get("messages", [])
        
        # Find the task description from HumanMessage
        task_description = ""
        for msg in messages:
            if isinstance(msg, HumanMessage):
                if isinstance(msg.content, str):
                    task_description = msg.content
                elif isinstance(msg.content, list):
                    # Handle multimodal content
                    for item in msg.content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            task_description = item.get("text", "")
                            break
                break
        
        if not task_description:
            # Fallback: try to get from input directly
            task_description = input.get("task_description", input.get("description", ""))
        
        if not task_description:
            error_msg = AIMessage(
                content="❌ Error: No task description provided. Please provide a description of the research task."
            )
            return {"messages": [error_msg]}
        
        # Create Denario workflow state
        # The workflow expects messages with the data description in the last HumanMessage
        denario_state: DenarioWorkflowState = {
            "messages": [HumanMessage(content=task_description)],
            "data_description": task_description,
            "idea": "",
            "methodology": "",
            "results": "",
            "project_dir": "",  # Will be set by initialize_denario
            "current_step": "",
            "error": "",
            "keys": None,  # Will be initialized by initialize_denario
        }
        
        # Run the workflow with streaming to capture intermediate states
        config = config or {"configurable": {"thread_id": f"denario_{os.getpid()}"}}
        
        try:
            # Use stream to get intermediate states
            all_messages = []
            last_state = None
            
            for chunk in self.workflow.stream(denario_state, config):
                # Extract state from chunk
                for node_name, node_state in chunk.items():
                    last_state = node_state
                    
                    # Get messages from this state update
                    chunk_messages = node_state.get("messages", [])
                    if chunk_messages:
                        # Only add new messages (avoid duplicates)
                        for msg in chunk_messages:
                            if msg not in all_messages:
                                all_messages.append(msg)
                    
                    # Log state transitions
                    current_step = node_state.get("current_step", "")
                    if current_step:
                        print(f"📊 State Update from {node_name}: current_step = {current_step}")
            
            # Use the final state if we have it
            result = last_state if last_state else denario_state
            
            # Extract the final messages from the result
            result_messages = result.get("messages", []) if result else []
            
            # Use all collected messages if available
            if all_messages:
                result_messages = all_messages
            elif not result_messages:
                # If no messages, create a summary from the state
                summary_parts = []
                if result and result.get("idea"):
                    summary_parts.append(f"✅ Research Idea: Generated ({len(result.get('idea', ''))} chars)")
                if result and result.get("methodology"):
                    summary_parts.append(f"✅ Methodology: Generated ({len(result.get('methodology', ''))} chars)")
                if result and result.get("results"):
                    summary_parts.append(f"✅ Results: Generated ({len(result.get('results', ''))} chars)")
                if result and result.get("current_step") == "done":
                    summary_parts.append(f"✅ Paper: Generated")
                
                project_dir = result.get("project_dir", "") if result else ""
                if project_dir:
                    summary_parts.append(f"\n📁 Project Directory: {project_dir}")
                
                summary = "\n".join(summary_parts) if summary_parts else "Denario workflow completed."
                result_messages = [AIMessage(content=summary)]
            
            return {"messages": result_messages}
            
        except Exception as e:
            error_msg = AIMessage(
                content=f"❌ **Error running Denario workflow**\n\n**Error:** {str(e)}\n\n**State:** Failed during workflow execution\n\nPlease check the error and try again."
            )
            return {"messages": [error_msg]}
    
    def stream(
        self, 
        input: dict[str, Any], 
        config: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Stream the Denario workflow with real-time state updates.
        
        This method delegates to the underlying CompiledStateGraph's stream method,
        which will be called by SubAgentMiddleware with stream_mode=["updates", "values"].
        The workflow's stream method will yield chunks in format {node_name: state_update},
        and SubAgentMiddleware will extract messages from these chunks.
        
        Args:
            input: Input from sub-agent system (will be converted to DenarioWorkflowState)
            config: Optional configuration for the workflow
            **kwargs: Additional keyword arguments (may include stream_mode)
            
        Yields:
            Chunks from the underlying workflow stream in format {node_name: state_update}
        """
        # Extract messages from input
        messages = input.get("messages", [])
        
        # Find the task description from HumanMessage
        task_description = ""
        for msg in messages:
            if isinstance(msg, HumanMessage):
                if isinstance(msg.content, str):
                    task_description = msg.content
                elif isinstance(msg.content, list):
                    # Handle multimodal content
                    for item in msg.content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            task_description = item.get("text", "")
                            break
                break
        
        if not task_description:
            # Fallback: try to get from input directly
            task_description = input.get("task_description", input.get("description", ""))
        
        if not task_description:
            error_msg = AIMessage(
                content="❌ Error: No task description provided. Please provide a description of the research task."
            )
            # Return error in workflow state format
            yield {"error_handler": {"messages": [error_msg], "error": "No task description", "current_step": "error"}}
            return
        
        # Create Denario workflow state
        denario_state: DenarioWorkflowState = {
            "messages": [HumanMessage(content=task_description)],
            "data_description": task_description,
            "idea": "",
            "methodology": "",
            "results": "",
            "project_dir": "",
            "current_step": "",
            "error": "",
            "keys": None,
        }
        
        # Run the workflow with streaming
        # Use config from kwargs if provided (SubAgentMiddleware passes config here)
        workflow_config = config or kwargs.get("config") or {"configurable": {"thread_id": f"denario_{os.getpid()}"}}
        
        try:
            # Delegate to the underlying workflow's stream method
            # Extract stream_mode from kwargs if present (SubAgentMiddleware passes this)
            stream_mode = kwargs.get("stream_mode", None)
            
            # CompiledStateGraph.stream() accepts stream_mode as a keyword argument
            if stream_mode:
                for chunk in self.workflow.stream(denario_state, workflow_config, stream_mode=stream_mode):
                    yield chunk
            else:
                for chunk in self.workflow.stream(denario_state, workflow_config):
                    yield chunk
            
        except Exception as e:
            error_msg = AIMessage(
                content=f"❌ **Error running Denario workflow**\n\n**Error:** {str(e)}\n\n**State:** Failed during workflow execution\n\nPlease check the error and try again."
            )
            yield {"error_handler": {"messages": [error_msg], "error": str(e), "current_step": "error"}}

