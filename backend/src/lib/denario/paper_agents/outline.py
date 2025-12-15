"""Outline parser and validator for dynamic paper generation.

This module provides functions to read and validate paper outlines from the filesystem.
The outline must exist at /plan_outline.json on the filesystem root. No fallbacks are provided.
"""

import json
from pathlib import Path
from typing import Any


OUTLINE_PATH = Path("/plan_outline.json")


def load_outline(outline_path: Path | str | None = None) -> dict[str, Any]:
    """Load outline from filesystem.
    
    Reads plan_outline.json from the filesystem root. The file must exist;
    no fallback to default outline is provided.
    
    Args:
        outline_path: Optional custom path to outline file. Defaults to /plan_outline.json.
    
    Returns:
        Parsed outline dictionary with sections sorted by order field.
    
    Raises:
        FileNotFoundError: If outline file does not exist at the specified path.
        ValueError: If JSON is malformed or structure is invalid.
    """
    if outline_path is None:
        outline_path = OUTLINE_PATH
    else:
        outline_path = Path(outline_path)
    
    if not outline_path.exists():
        raise FileNotFoundError(
            f"plan_outline.json not found at {outline_path}. "
            "Please create outline first using the outline-agent."
        )
    
    try:
        with outline_path.open("r", encoding="utf-8") as f:
            outline = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in outline file {outline_path}: {e}"
        ) from e
    
    is_valid, error_msg = validate_outline(outline)
    if not is_valid:
        raise ValueError(
            f"Invalid outline structure in {outline_path}: {error_msg}"
        )
    
    # Sort sections by order field
    if "sections" in outline:
        outline["sections"] = sorted(
            outline["sections"],
            key=lambda s: s.get("order", 0)
        )
    
    return outline


def validate_outline(outline: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate outline structure.
    
    Checks that outline has required structure: sections array with each
    section having id, title, description, and order fields.
    
    Args:
        outline: Outline dictionary to validate.
    
    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not isinstance(outline, dict):
        return False, "Outline must be a dictionary"
    
    if "sections" not in outline:
        return False, "Outline must have 'sections' key"
    
    if not isinstance(outline["sections"], list):
        return False, "'sections' must be a list"
    
    if len(outline["sections"]) == 0:
        return False, "'sections' must not be empty"
    
    required_fields = {"id", "title", "description", "order"}
    section_ids = set()
    
    for i, section in enumerate(outline["sections"]):
        if not isinstance(section, dict):
            return False, f"Section {i} must be a dictionary"
        
        missing_fields = required_fields - set(section.keys())
        if missing_fields:
            return False, f"Section {i} missing required fields: {missing_fields}"
        
        section_id = section.get("id")
        if section_id in section_ids:
            return False, f"Duplicate section ID: {section_id}"
        section_ids.add(section_id)
        
        if not isinstance(section.get("order"), int):
            return False, f"Section {i} 'order' must be an integer"
    
    return True, None


def get_default_outline() -> dict[str, Any]:
    """Get default 4-section outline for testing purposes only.
    
    This function is provided for unit testing and development. It should
    NOT be used in production. Production code must read outline from filesystem.
    
    Returns:
        Default outline with Introduction, Methods, Results, Conclusions sections.
    """
    return {
        "sections": [
            {
                "id": "introduction",
                "title": "Introduction",
                "description": "Background, motivation, and contributions",
                "order": 1,
            },
            {
                "id": "methods",
                "title": "Methods",
                "description": "Methodology and approach",
                "order": 2,
            },
            {
                "id": "results",
                "title": "Results",
                "description": "Experimental results and findings",
                "order": 3,
            },
            {
                "id": "conclusions",
                "title": "Conclusions",
                "description": "Summary and future work",
                "order": 4,
            },
        ]
    }

