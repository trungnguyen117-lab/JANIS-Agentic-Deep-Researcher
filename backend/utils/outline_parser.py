"""Utility functions for parsing structured outlines from planning agent messages."""

import json
import re
from typing import Any, Dict, List, Optional


def extract_outline_from_message(message_content: str) -> Optional[Dict[str, Any]]:
    """Extract structured outline from planning agent message.
    
    Looks for the ```OUTLINE marker and extracts the JSON content.
    
    Args:
        message_content: The full message content from the planning agent
        
    Returns:
        Dictionary containing the parsed outline, or None if not found
        
    Example:
        >>> content = "```OUTLINE\\n{\"sections\": [...]}\\n```"
        >>> outline = extract_outline_from_message(content)
    """
    # Pattern to match ```OUTLINE ... ```
    pattern = r'```OUTLINE\s*\n(.*?)\n```'
    match = re.search(pattern, message_content, re.DOTALL)
    
    if not match:
        # Try alternative format without backticks
        pattern = r'OUTLINE\s*\n(.*?)(?=\n```|\n\n|$)'
        match = re.search(pattern, message_content, re.DOTALL)
    
    if not match:
        return None
    
    outline_text = match.group(1).strip()
    
    try:
        outline = json.loads(outline_text)
        return outline
    except json.JSONDecodeError:
        # Try to fix common JSON issues
        # Remove trailing commas
        outline_text = re.sub(r',\s*}', '}', outline_text)
        outline_text = re.sub(r',\s*]', ']', outline_text)
        
        try:
            outline = json.loads(outline_text)
            return outline
        except json.JSONDecodeError:
            return None


def validate_outline(outline: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate that the outline has the required structure.
    
    Args:
        outline: The outline dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(outline, dict):
        return False, "Outline must be a dictionary"
    
    if "sections" not in outline:
        return False, "Outline must contain 'sections' key"
    
    sections = outline["sections"]
    if not isinstance(sections, list):
        return False, "Sections must be a list"
    
    if len(sections) == 0:
        return False, "Outline must contain at least one section"
    
    required_fields = ["id", "title", "description", "order"]
    section_ids = set()
    orders = set()
    
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            return False, f"Section {i} must be a dictionary"
        
        # Check required fields
        for field in required_fields:
            if field not in section:
                return False, f"Section {i} missing required field: {field}"
        
        # Check for duplicate IDs
        section_id = section["id"]
        if section_id in section_ids:
            return False, f"Duplicate section ID: {section_id}"
        section_ids.add(section_id)
        
        # Check for duplicate orders
        order = section["order"]
        if order in orders:
            return False, f"Duplicate section order: {order}"
        orders.add(order)
        
        # Validate field types
        if not isinstance(section["id"], str):
            return False, f"Section {i} 'id' must be a string"
        if not isinstance(section["title"], str):
            return False, f"Section {i} 'title' must be a string"
        if not isinstance(section["description"], str):
            return False, f"Section {i} 'description' must be a string"
        if not isinstance(section["order"], int):
            return False, f"Section {i} 'order' must be an integer"
    
    return True, None


def parse_and_validate_outline(message_content: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Extract and validate outline from message content.
    
    Args:
        message_content: The full message content from the planning agent
        
    Returns:
        Tuple of (outline_dict, error_message)
        If successful, error_message is None
        If failed, outline_dict is None and error_message contains the reason
    """
    outline = extract_outline_from_message(message_content)
    
    if outline is None:
        return None, "Could not extract outline from message. Make sure it contains ```OUTLINE marker with valid JSON."
    
    is_valid, error = validate_outline(outline)
    
    if not is_valid:
        return None, f"Invalid outline structure: {error}"
    
    return outline, None


def get_sections_sorted_by_order(outline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get sections from outline sorted by order.
    
    Args:
        outline: The outline dictionary
        
    Returns:
        List of sections sorted by their order field
    """
    if "sections" not in outline:
        return []
    
    sections = outline["sections"]
    return sorted(sections, key=lambda s: s.get("order", 0))


def get_section_by_id(outline: Dict[str, Any], section_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific section by its ID.
    
    Args:
        outline: The outline dictionary
        section_id: The ID of the section to retrieve
        
    Returns:
        The section dictionary, or None if not found
    """
    if "sections" not in outline:
        return None
    
    for section in outline["sections"]:
        if section.get("id") == section_id:
            return section
    
    return None

