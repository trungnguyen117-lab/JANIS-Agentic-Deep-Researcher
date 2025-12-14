"""Simple outline creation tool that writes to regular filesystem (no deepagents)."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from langchain.tools import StructuredTool

logger = logging.getLogger(__name__)


def extract_thread_id_from_config(config: Any) -> str | None:
    """Extract thread_id from LangGraph RunnableConfig.
    
    Tries multiple methods to extract thread_id from the config object.
    Returns None if not found.
    """
    if not config:
        return None
    
    thread_id = None
    
    # Method 1: Check config.configurable (dict-like access)
    if hasattr(config, 'configurable'):
        configurable = config.configurable
        if isinstance(configurable, dict):
            thread_id = configurable.get('thread_id')
        elif hasattr(configurable, 'get'):
            thread_id = configurable.get('thread_id')
        # Also try direct attribute access
        if not thread_id and hasattr(configurable, 'thread_id'):
            thread_id = configurable.thread_id
        # Try dict-like access with __getitem__
        if not thread_id:
            try:
                if hasattr(configurable, '__getitem__'):
                    thread_id = configurable['thread_id']
            except (KeyError, TypeError):
                pass
    
    # Method 2: Check if config is a dict-like object
    if not thread_id and hasattr(config, 'get'):
        try:
            configurable = config.get('configurable', {})
            if isinstance(configurable, dict):
                thread_id = configurable.get('thread_id')
        except Exception:
            pass
    
    # Method 3: Check config directly (some LangGraph versions store it here)
    if not thread_id and hasattr(config, 'thread_id'):
        thread_id = config.thread_id
    
    # Method 4: Try accessing as attributes
    if not thread_id:
        try:
            if hasattr(config, '__dict__'):
                thread_id = config.__dict__.get('thread_id')
        except Exception:
            pass
    
    return thread_id

# Use project directory relative to backend folder
# Default to ./project/plan_outline.json (relative to backend directory)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # Go up to project root
OUTLINE_FILE_PATH = str(_PROJECT_ROOT / "project" / "plan_outline.json")


def create_outline(
    sections: list[dict[str, Any]],
    output_path: str | None = None,
    config: Any | None = None,
) -> str:
    """Create a paper outline and save it to a JSON file.
    
    Args:
        sections: List of section dictionaries, each with:
            - id: Unique identifier (e.g., "intro", "methods")
            - title: Section title (e.g., "Introduction", "Methods")
            - description: What should be covered in this section
            - order: Integer indicating order (1, 2, 3, ...)
            - estimatedDepth: Optional string (e.g., "2-3 pages")
            - subsections: Optional list of subsection titles
        output_path: Path where to save the outline JSON file (default: project/plan_outline.json in project root)
    
    Returns:
        str: Success message with path to saved outline
    """
    try:
        # Try to get config from parameter or from execution context
        if not config:
            try:
                from langchain_core.runnables import get_config
                config = get_config()
                logger.debug(f"Got config from get_config(): {type(config)}")
            except Exception as e:
                logger.debug(f"Could not get config from get_config(): {e}")
        
        # Extract thread_id using helper function
        thread_id = extract_thread_id_from_config(config)
        
        # Debug logging with detailed inspection
        if thread_id:
            logger.info(f"✅ Extracted thread_id: {thread_id}")
            print(f"[Outline] ✅ Extracted thread_id: {thread_id}", flush=True)
        else:
            logger.warning(f"⚠️ Could not extract thread_id from config. Config type: {type(config)}")
            print(f"[Outline] ⚠️ Could not extract thread_id. Config type: {type(config)}", flush=True)
            if config:
                logger.debug(f"Config attributes: {dir(config)}")
                if hasattr(config, 'configurable'):
                    logger.debug(f"Config.configurable: {config.configurable}, type: {type(config.configurable)}")
                    # Try to print the actual configurable content
                    try:
                        if isinstance(config.configurable, dict):
                            logger.debug(f"Config.configurable keys: {list(config.configurable.keys())}")
                            print(f"[Outline] Config.configurable keys: {list(config.configurable.keys())}", flush=True)
                        elif hasattr(config.configurable, '__dict__'):
                            logger.debug(f"Config.configurable.__dict__: {config.configurable.__dict__}")
                            print(f"[Outline] Config.configurable.__dict__: {config.configurable.__dict__}", flush=True)
                        elif hasattr(config.configurable, '__getitem__'):
                            # Try to access like a dict
                            try:
                                keys = list(config.configurable.keys()) if hasattr(config.configurable, 'keys') else []
                                logger.debug(f"Config.configurable (dict-like) keys: {keys}")
                                print(f"[Outline] Config.configurable (dict-like) keys: {keys}", flush=True)
                            except Exception:
                                pass
                    except Exception as e:
                        logger.debug(f"Error inspecting config.configurable: {e}")
                        print(f"[Outline] Error inspecting config.configurable: {e}", flush=True)
        
        # Use thread-based path - REQUIRED, no fallbacks
        if output_path is None:
            if thread_id:
                output_path = str(_PROJECT_ROOT / "project" / "threads" / str(thread_id) / "plan_outline.json")
                # Ensure thread directory exists
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Using thread-specific outline path: {output_path}")
                print(f"[Outline] ✅ Thread ID: {thread_id} - Using isolated directory: {Path(output_path).parent}", flush=True)
            else:
                error_msg = "❌ No thread_id found in config. Thread-based file storage is required. Cannot create outline without thread_id."
                logger.error(error_msg)
                print(f"[Outline] {error_msg}", flush=True)
                raise ValueError(error_msg)
        
        # Validate sections
        if not isinstance(sections, list) or len(sections) == 0:
            raise ValueError("sections must be a non-empty list")
        
        # Validate each section
        required_fields = {"id", "title", "description", "order"}
        section_ids = set()
        
        for i, section in enumerate(sections):
            if not isinstance(section, dict):
                raise ValueError(f"Section {i} must be a dictionary")
            
            missing_fields = required_fields - set(section.keys())
            if missing_fields:
                raise ValueError(f"Section {i} missing required fields: {missing_fields}")
            
            section_id = section.get("id")
            if section_id in section_ids:
                raise ValueError(f"Duplicate section ID: {section_id}")
            section_ids.add(section_id)
            
            if not isinstance(section.get("order"), int):
                raise ValueError(f"Section {i} 'order' must be an integer")
        
        # Sort sections by order
        sections_sorted = sorted(sections, key=lambda x: x.get("order", 0))
        
        # Create outline structure
        outline = {
            "sections": sections_sorted
        }
        
        # Write to filesystem
        output_file = Path(output_path)
        # Ensure parent directory exists and is writable
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if we can write to the directory
        if not os.access(output_file.parent, os.W_OK):
            raise PermissionError(f"Cannot write to directory: {output_file.parent}")
        
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(outline, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Outline created successfully with {len(sections_sorted)} sections at {output_path}")
        
        # Return both success message AND the outline JSON for frontend
        # Format: SUCCESS_MESSAGE\n\nOUTLINE_JSON_START\n{json}\nOUTLINE_JSON_END
        outline_json_str = json.dumps(outline, indent=2, ensure_ascii=False)
        return f"✅ Outline created successfully with {len(sections_sorted)} sections and saved to {output_path}\n\nOUTLINE_JSON_START\n{outline_json_str}\nOUTLINE_JSON_END"
        
    except Exception as e:
        error_msg = f"❌ Error creating outline: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


# Context variable to store config (set by tools_node)
import contextvars
_config_var = contextvars.ContextVar('langgraph_config', default=None)

# Make the tool configurable to receive RunnableConfig
def _create_outline_wrapper(sections: list[dict[str, Any]], output_path: str | None = None, **kwargs):
    """Wrapper to extract config from execution context or contextvars."""
    # Try to get config from contextvars first (set by tools_node)
    config = _config_var.get()
    
    # If not in contextvars, try get_config()
    if not config:
        try:
            from langchain_core.runnables import get_config
            config = get_config()
            logger.debug(f"Wrapper: Got config from get_config(): {type(config)}")
        except Exception as e:
            logger.debug(f"Wrapper: Could not get config from get_config(): {e}")
    
    return create_outline(sections=sections, output_path=output_path, config=config)

# Create the tool
create_outline_tool = StructuredTool.from_function(
    name="create_outline",
    description="Create a structured paper outline and save it to a JSON file. Use this to create the outline structure for scientific papers. The outline will be saved to project/plan_outline.json (or project/threads/{thread_id}/plan_outline.json for thread-specific storage) and used by the paper generation system.",
    func=_create_outline_wrapper,
)

