"""Denario workflow as the main fixed research workflow.
Maps directly to Denario method calls:
- den.set_data_description() → initialize_denario()
- den.get_idea() → generate_idea()
- den.get_method() → generate_method()
- den.get_results() → generate_results()
- den.get_paper() → generate_paper()
"""

import os
from pathlib import Path
from typing import TypedDict, Annotated, Any, NotRequired
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# Import denario components
import sys
from pathlib import Path as PathLib

_project_root = PathLib(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from denario import Denario, Research, Journal, LLM, models, KeyManager
from denario.config import INPUT_FILES, IDEA_FILE, METHOD_FILE, RESULTS_FILE


class DenarioWorkflowState(TypedDict):
    """State for Denario workflow - maps to Denario Research object."""
    messages: Annotated[list[AnyMessage], add_messages]
    data_description: str
    idea: str
    methodology: str
    results: str
    project_dir: str
    current_step: str  # 'initialize', 'idea', 'method', 'results', 'paper', 'done', 'error'
    error: str
    keys: KeyManager
    # Additional state for frontend display
    step_progress: NotRequired[dict[str, Any]]  # Progress info for each step


def initialize_denario(state: DenarioWorkflowState) -> DenarioWorkflowState:
    """Initialize Denario instance - equivalent to den.set_data_description()"""
    step_name = "🔧 INITIALIZE"
    print(f"\n{'='*60}")
    print(f"{step_name}")
    print(f"{'='*60}")
    
    # Get data description from user message
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, HumanMessage):
            data_description = last_message.content
        else:
            data_description = state.get("data_description", "")
    else:
        data_description = state.get("data_description", "")
    
    if not data_description:
        error_msg = "No data description provided. Please provide a data description."
        print(f"❌ ERROR: {error_msg}")
        return {
            "error": error_msg,
            "current_step": "error",
        }
    
    # Set up project directory
    project_dir = state.get("project_dir")
    if not project_dir:
        project_dir = os.path.join(os.getcwd(), "denario_project")
        os.makedirs(project_dir, exist_ok=True)
    
    print(f"📁 Project Directory: {project_dir}")
    print(f"📝 Data Description Length: {len(data_description)} characters")
    
    # Initialize KeyManager
    keys = KeyManager()
    keys.get_keys_from_env()
    print(f"🔑 API Keys: Initialized")
    
    # Create Denario instance and set data description (equivalent to den.set_data_description())
    denario = Denario(
        research=Research(),
        project_dir=project_dir,
        clear_project_dir=False,
    )
    denario.set_data_description(data_description)
    
    # Add initialization message
    init_content = f"""🔧 **Denario Workflow Initialized**

**State:** Initialized ✓
**Project Directory:** `{project_dir}`
**Data Description:** {len(data_description)} characters
**Current Step:** Idea Generation

Starting research idea generation..."""
    
    init_message = AIMessage(content=init_content)
    new_messages = list(messages) + [init_message] if messages else [init_message]
    
    print(f"✅ {step_name} completed\n")
    
    return {
        "messages": new_messages,
        "data_description": data_description,
        "project_dir": project_dir,
        "keys": keys,
        "current_step": "idea",
        "idea": "",
        "methodology": "",
        "results": "",
        "error": "",
        "step_progress": {
            "initialize": {"status": "completed", "project_dir": project_dir}
        }
    }


def generate_idea(state: DenarioWorkflowState) -> DenarioWorkflowState:
    """Generate research idea - equivalent to den.get_idea() / den.get_idea_fast()"""
    step_name = "💡 STEP 1: GENERATE IDEA"
    print(f"\n{'='*60}")
    print(f"{step_name}")
    print(f"{'='*60}")
    
    try:
        # Create Denario instance
        denario = Denario(
            research=Research(),
            project_dir=state["project_dir"],
            clear_project_dir=False,
        )
        
        # Set data description (equivalent to den.set_data_description())
        denario.set_data_description(state["data_description"])
        
        # Generate idea using fast mode (equivalent to den.get_idea_fast())
        denario.get_idea_fast(llm=models["gemini-2.0-flash"])
        
        # Read generated idea
        idea_file = os.path.join(state["project_dir"], INPUT_FILES, IDEA_FILE)
        if os.path.exists(idea_file):
            with open(idea_file, 'r', encoding='utf-8') as f:
                idea_content = f.read()
        else:
            idea_content = denario.research.idea
        
        print(f"✅ Idea generated: {len(idea_content)} characters")
        
        # Add progress message
        progress_content = f"""💡 **Step 1: Research Idea Generated** ✓

**State:** Idea Generation Complete
**Current Step:** Methodology Generation
**Idea Length:** {len(idea_content)} characters
**Idea File:** `{idea_file if os.path.exists(idea_file) else 'In memory'}`

**Idea Preview:**
{idea_content[:500]}{'...' if len(idea_content) > 500 else ''}

**Next Step:** Generating research methodology..."""
        
        progress_msg = AIMessage(content=progress_content)
        new_messages = list(state.get("messages", [])) + [progress_msg]
        
        return {
            "messages": new_messages,
            "idea": idea_content,
            "current_step": "method",
            "step_progress": {
                **state.get("step_progress", {}),
                "idea": {"status": "completed", "length": len(idea_content), "file": idea_file}
            }
        }
    except Exception as e:
        error_msg = AIMessage(content=f"❌ **Error in Step 1: Idea Generation**\n\n**Error:** {str(e)}")
        new_messages = list(state.get("messages", [])) + [error_msg]
        return {
            "messages": new_messages,
            "error": f"Error generating idea: {str(e)}",
            "current_step": "error",
        }


def generate_method(state: DenarioWorkflowState) -> DenarioWorkflowState:
    """Generate research methodology - equivalent to den.get_method() / den.get_method_fast()"""
    step_name = "📐 STEP 2: GENERATE METHODOLOGY"
    print(f"\n{'='*60}")
    print(f"{step_name}")
    print(f"{'='*60}")
    
    try:
        denario = Denario(
            research=Research(),
            project_dir=state["project_dir"],
            clear_project_dir=False,
        )
        
        # Set data description and idea
        denario.set_data_description(state["data_description"])
        denario.set_idea(state["idea"])
        
        # Generate method using fast mode (equivalent to den.get_method_fast())
        denario.get_method_fast(llm=models["gemini-2.0-flash"])
        
        # Read generated methodology
        method_file = os.path.join(state["project_dir"], INPUT_FILES, METHOD_FILE)
        if os.path.exists(method_file):
            with open(method_file, 'r', encoding='utf-8') as f:
                method_content = f.read()
        else:
            method_content = denario.research.methodology
        
        print(f"✅ Methodology generated: {len(method_content)} characters")
        
        # Add progress message
        progress_content = f"""📐 **Step 2: Research Methodology Generated** ✓

**State:** Methodology Generation Complete
**Current Step:** Results Generation
**Methodology Length:** {len(method_content)} characters

**Next Step:** Generating research results (this may take longer)..."""
        
        progress_msg = AIMessage(content=progress_content)
        new_messages = list(state.get("messages", [])) + [progress_msg]
        
        return {
            "messages": new_messages,
            "methodology": method_content,
            "current_step": "results",
            "step_progress": {
                **state.get("step_progress", {}),
                "method": {"status": "completed", "length": len(method_content), "file": method_file}
            }
        }
    except Exception as e:
        error_msg = AIMessage(content=f"❌ **Error in Step 2: Methodology Generation**\n\n**Error:** {str(e)}")
        new_messages = list(state.get("messages", [])) + [error_msg]
        return {
            "messages": new_messages,
            "error": f"Error generating methodology: {str(e)}",
            "current_step": "error",
        }


def generate_results(state: DenarioWorkflowState) -> DenarioWorkflowState:
    """Generate research results - equivalent to den.get_results()"""
    step_name = "🔬 STEP 3: GENERATE RESULTS"
    print(f"\n{'='*60}")
    print(f"{step_name}")
    print(f"{'='*60}")
    
    try:
        denario = Denario(
            research=Research(),
            project_dir=state["project_dir"],
            clear_project_dir=False,
        )
        
        # Set all research data
        denario.set_data_description(state["data_description"])
        denario.set_idea(state["idea"])
        denario.set_method(state["methodology"])
        
        # Generate results (equivalent to den.get_results())
        denario.get_results(involved_agents=['engineer', 'researcher'])
        
        # Read generated results
        results_file = os.path.join(state["project_dir"], INPUT_FILES, RESULTS_FILE)
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                results_content = f.read()
        else:
            results_content = denario.research.results
        
        # Check for plots
        plots_dir = os.path.join(state["project_dir"], INPUT_FILES, "plots")
        plot_count = len([f for f in os.listdir(plots_dir) if os.path.isfile(os.path.join(plots_dir, f))]) if os.path.exists(plots_dir) else 0
        
        print(f"✅ Results generated: {len(results_content)} characters, {plot_count} plots")
        
        # Add progress message
        progress_content = f"""🔬 **Step 3: Research Results Generated** ✓

**State:** Results Generation Complete
**Current Step:** Paper Generation
**Results Length:** {len(results_content)} characters
**Generated Plots:** {plot_count}

**Next Step:** Generating LaTeX paper..."""
        
        progress_msg = AIMessage(content=progress_content)
        new_messages = list(state.get("messages", [])) + [progress_msg]
        
        return {
            "messages": new_messages,
            "results": results_content,
            "current_step": "paper",
            "step_progress": {
                **state.get("step_progress", {}),
                "results": {"status": "completed", "length": len(results_content), "plots": plot_count}
            }
        }
    except Exception as e:
        error_msg = AIMessage(content=f"❌ **Error in Step 3: Results Generation**\n\n**Error:** {str(e)}\n\n**Note:** This step requires cmbagent.")
        new_messages = list(state.get("messages", [])) + [error_msg]
        return {
            "messages": new_messages,
            "error": f"Error generating results: {str(e)}",
            "current_step": "error",
        }


def generate_paper(state: DenarioWorkflowState) -> DenarioWorkflowState:
    """Generate research paper - equivalent to den.get_paper()"""
    step_name = "📄 STEP 4: GENERATE PAPER"
    print(f"\n{'='*60}")
    print(f"{step_name}")
    print(f"{'='*60}")
    
    try:
        denario = Denario(
            research=Research(),
            project_dir=state["project_dir"],
            clear_project_dir=False,
        )
        
        # Load all research data
        denario.set_all()
        
        # Generate paper (equivalent to den.get_paper())
        denario.get_paper(
            journal=Journal.NONE,
            llm=models["gemini-2.5-flash"],
            writer="scientist",
            add_citations=True,
        )
        
        # Find generated paper files
        paper_dir = os.path.join(state["project_dir"], "paper")
        paper_files = [f.name for f in Path(paper_dir).glob("*.tex")] if os.path.exists(paper_dir) else []
        
        print(f"✅ Paper generated: {len(paper_files)} LaTeX files")
        
        # Add completion message
        completion_content = f"""🎉 **Denario Workflow Completed Successfully!**

**Final State:** All Steps Complete ✓

**Workflow Summary:**
✅ Step 1: Research Idea - Generated ({len(state.get('idea', ''))} chars)
✅ Step 2: Methodology - Generated ({len(state.get('methodology', ''))} chars)
✅ Step 3: Results - Generated ({len(state.get('results', ''))} chars)
✅ Step 4: Paper - Generated ({len(paper_files)} LaTeX files)

**Project Directory:** `{state["project_dir"]}`

All research outputs have been generated and saved."""
        
        completion_msg = AIMessage(content=completion_content)
        new_messages = list(state.get("messages", [])) + [completion_msg]
        
        return {
            "messages": new_messages,
            "current_step": "done",
            "step_progress": {
                **state.get("step_progress", {}),
                "paper": {"status": "completed", "files": len(paper_files), "directory": paper_dir}
            }
        }
    except Exception as e:
        error_msg = AIMessage(content=f"❌ **Error in Step 4: Paper Generation**\n\n**Error:** {str(e)}")
        new_messages = list(state.get("messages", [])) + [error_msg]
        return {
            "messages": new_messages,
            "error": f"Error generating paper: {str(e)}",
            "current_step": "error",
        }


def error_handler(state: DenarioWorkflowState) -> DenarioWorkflowState:
    """Handle errors in workflow."""
    error = state.get("error", "Unknown error")
    error_msg = AIMessage(content=f"❌ Error in Denario workflow: {error}\n\nPlease check the error and try again.")
    new_messages = list(state.get("messages", [])) + [error_msg]
    return {
        "messages": new_messages,
        "step_progress": state.get("step_progress", {})  # Preserve existing progress
    }


def create_denario_workflow():
    """Create the Denario workflow graph - maps to Denario method calls."""
    builder = StateGraph(DenarioWorkflowState)
    
    # Add nodes - each maps to a Denario method
    builder.add_node("initialize", initialize_denario)  # den.set_data_description()
    builder.add_node("generate_idea", generate_idea)    # den.get_idea()
    builder.add_node("generate_method", generate_method)  # den.get_method()
    builder.add_node("generate_results", generate_results)  # den.get_results()
    builder.add_node("generate_paper", generate_paper)  # den.get_paper()
    builder.add_node("error_handler", error_handler)
    
    # Simple sequential flow
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "generate_idea")
    
    # Check for errors after each step
    builder.add_conditional_edges(
        "generate_idea",
        lambda state: "error_handler" if state.get("error") else "generate_method",
        {"generate_method": "generate_method", "error_handler": "error_handler"}
    )
    
    builder.add_conditional_edges(
        "generate_method",
        lambda state: "error_handler" if state.get("error") else "generate_results",
        {"generate_results": "generate_results", "error_handler": "error_handler"}
    )
    
    builder.add_conditional_edges(
        "generate_results",
        lambda state: "error_handler" if state.get("error") else "generate_paper",
        {"generate_paper": "generate_paper", "error_handler": "error_handler"}
    )
    
    builder.add_edge("generate_paper", END)
    builder.add_edge("error_handler", END)
    
    # Compile with checkpointer
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    
    return graph