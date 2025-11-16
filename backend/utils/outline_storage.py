"""Utility functions for saving and loading plan outline."""

import json
from pathlib import Path
from typing import Any, Dict, Optional


def save_outline_to_file(outline: Dict[str, Any], file_path: str = "/plan_outline.json") -> bool:
    """Save outline to a JSON file.
    
    Args:
        outline: The outline dictionary to save
        file_path: Path where to save the outline (default: /plan_outline.json)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure file_path starts with /
        if not file_path.startswith("/"):
            file_path = f"/{file_path}"
        
        outline_json = json.dumps(outline, indent=2, ensure_ascii=False)
        
        # Note: This function is meant to be used with the filesystem tools
        # The actual file writing will be done by the agent using write_file tool
        # This function just prepares the JSON string
        return True
    except Exception:
        return False


def load_outline_from_file(file_path: str = "/plan_outline.json") -> Optional[Dict[str, Any]]:
    """Load outline from a JSON file.
    
    Args:
        file_path: Path to the outline file (default: /plan_outline.json)
        
    Returns:
        The outline dictionary, or None if file doesn't exist or is invalid
    """
    try:
        # Ensure file_path starts with /
        if not file_path.startswith("/"):
            file_path = f"/{file_path}"
        
        # Note: This function is meant to be used with the filesystem tools
        # The actual file reading will be done by the agent using read_file tool
        # This function would parse the JSON content
        return None
    except Exception:
        return None


def parse_outline_json(json_content: str) -> Optional[Dict[str, Any]]:
    """Parse outline from JSON string content.
    
    Args:
        json_content: JSON string content from a file
        
    Returns:
        The outline dictionary, or None if parsing fails
    """
    try:
        outline = json.loads(json_content)
        return outline
    except json.JSONDecodeError:
        return None


def update_outline_section(
    outline: Dict[str, Any],
    section_id: str,
    updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Update a specific section in the outline.
    
    Args:
        outline: The outline dictionary
        section_id: ID of the section to update
        updates: Dictionary of fields to update
        
    Returns:
        Updated outline dictionary, or None if section not found
    """
    if "sections" not in outline:
        return None
    
    for section in outline["sections"]:
        if section.get("id") == section_id:
            section.update(updates)
            return outline
    
    return None


def add_outline_section(
    outline: Dict[str, Any],
    section: Dict[str, Any]
) -> Dict[str, Any]:
    """Add a new section to the outline.
    
    Args:
        outline: The outline dictionary
        section: The new section dictionary to add
        
    Returns:
        Updated outline dictionary
    """
    if "sections" not in outline:
        outline["sections"] = []
    
    outline["sections"].append(section)
    return outline


def remove_outline_section(
    outline: Dict[str, Any],
    section_id: str
) -> Optional[Dict[str, Any]]:
    """Remove a section from the outline.
    
    Args:
        outline: The outline dictionary
        section_id: ID of the section to remove
        
    Returns:
        Updated outline dictionary, or None if section not found
    """
    if "sections" not in outline:
        return None
    
    sections = outline["sections"]
    for i, section in enumerate(sections):
        if section.get("id") == section_id:
            sections.pop(i)
            return outline
    
    return None


def reorder_outline_sections(
    outline: Dict[str, Any],
    new_order: list[str]
) -> Optional[Dict[str, Any]]:
    """Reorder sections in the outline.
    
    Args:
        outline: The outline dictionary
        new_order: List of section IDs in the desired order
        
    Returns:
        Updated outline dictionary with sections reordered, or None if invalid
    """
    if "sections" not in outline:
        return None
    
    sections = outline["sections"]
    section_map = {section["id"]: section for section in sections}
    
    # Verify all IDs exist
    if len(new_order) != len(sections) or set(new_order) != set(section_map.keys()):
        return None
    
    # Reorder and update order numbers
    reordered_sections = [section_map[sid] for sid in new_order]
    for i, section in enumerate(reordered_sections, start=1):
        section["order"] = i
    
    outline["sections"] = reordered_sections
    return outline

