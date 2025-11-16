"""JSON validation tool for verifying JSON syntax and structure."""

import json
from typing import Dict, Any, Optional
from langchain_core.tools import tool


@tool
def validate_json(json_string: str, file_path: Optional[str] = None) -> str:
    """Validate JSON syntax and structure.
    
    Use this tool to verify that a JSON string is valid before writing it to a file.
    This is especially important for plan_outline.json which must be valid JSON for the frontend to parse.
    
    IMPORTANT: If you want to validate a file that's already written:
    1. First use read_file("/plan_outline.json") to read the file content
    2. Then call validate_json(json_string="<the file content>") to validate it
    
    Args:
        json_string: The JSON string to validate. If validating a file, read the file first and pass its content here.
        file_path: Optional file path for reference. This is just for documentation - the tool validates json_string.
    
    Returns:
        A detailed validation result message indicating:
        - Whether the JSON is valid
        - If invalid, the specific error and location (line, column, problematic line)
        - If valid, confirmation and basic structure information (sections count, required fields)
    
    Examples:
        validate_json('{"sections": [{"id": "section_1"}]}')
        # To validate a file: read_file("/plan_outline.json") first, then:
        validate_json(json_string="<file content from read_file>", file_path="/plan_outline.json")
    """
    result_parts = []
    
    # If file_path is provided, mention it in the response
    if file_path:
        result_parts.append(f"Validating JSON for file: {file_path}")
        result_parts.append("Note: Make sure you read the file content first using read_file, then pass it as json_string")
        result_parts.append("")
    
    # Validate the JSON string
    if not json_string or not json_string.strip():
        return "❌ ERROR: JSON string is empty or contains only whitespace. Please provide a valid JSON string."
    
    try:
        # Parse the JSON to check syntax
        parsed = json.loads(json_string)
        
        # Basic structure validation
        validation_checks = []
        
        # Check if it's an object (dict)
        if isinstance(parsed, dict):
            validation_checks.append("✓ Valid JSON object (dictionary)")
            
            # Check for required fields if it's an outline
            if "sections" in parsed:
                validation_checks.append("✓ Contains 'sections' field")
                sections = parsed.get("sections", [])
                if isinstance(sections, list):
                    validation_checks.append(f"✓ 'sections' is an array with {len(sections)} items")
                    
                    # Validate each section
                    for i, section in enumerate(sections):
                        if not isinstance(section, dict):
                            validation_checks.append(f"⚠ Section {i+1} is not an object")
                        else:
                            required_fields = ["id", "title", "description", "order"]
                            missing_fields = [field for field in required_fields if field not in section]
                            if missing_fields:
                                validation_checks.append(f"⚠ Section {i+1} missing fields: {', '.join(missing_fields)}")
                            else:
                                validation_checks.append(f"✓ Section {i+1} has all required fields")
                            
                            # Validate subsections if present
                            if "subsections" in section:
                                if not isinstance(section["subsections"], list):
                                    validation_checks.append(f"⚠ Section {i+1} 'subsections' is not an array")
                                else:
                                    validation_checks.append(f"✓ Section {i+1} has {len(section['subsections'])} subsections")
                                    for j, subsection in enumerate(section["subsections"]):
                                        if not isinstance(subsection, dict):
                                            validation_checks.append(f"⚠ Section {i+1}, Subsection {j+1} is not an object")
                                        else:
                                            subsection_required_fields = ["id", "title", "description", "order"]
                                            subsection_missing_fields = [field for field in subsection_required_fields if field not in subsection]
                                            if subsection_missing_fields:
                                                validation_checks.append(f"⚠ Section {i+1}, Subsection {j+1} missing fields: {', '.join(subsection_missing_fields)}")
                                            else:
                                                validation_checks.append(f"✓ Section {i+1}, Subsection {j+1} has all required fields")
                            else:
                                validation_checks.append(f"ℹ Section {i+1} has no 'subsections' array (recommended for better structure)")
                else:
                    validation_checks.append("⚠ 'sections' is not an array")
            else:
                validation_checks.append("ℹ No 'sections' field found (may not be an outline)")
        elif isinstance(parsed, list):
            validation_checks.append("✓ Valid JSON array")
        else:
            validation_checks.append("✓ Valid JSON (primitive value)")
        
        # Success message
        result_parts.append("✅ JSON is VALID")
        result_parts.append("")
        result_parts.append("Validation details:")
        result_parts.extend(validation_checks)
        
        return "\n".join(result_parts)
        
    except json.JSONDecodeError as e:
        # Detailed error information
        error_msg = f"❌ JSON is INVALID"
        result_parts.append(error_msg)
        result_parts.append("")
        result_parts.append(f"Error: {e.msg}")
        result_parts.append(f"Location: Line {e.lineno}, Column {e.colno}")
        
        # Show the problematic line if possible
        if e.lineno and json_string:
            lines = json_string.split('\n')
            if e.lineno <= len(lines):
                problem_line = lines[e.lineno - 1]
                result_parts.append(f"Problem line: {problem_line}")
                # Show pointer to the column
                if e.colno:
                    pointer = " " * (e.colno - 1) + "^"
                    result_parts.append(f"            {pointer}")
        
        result_parts.append("")
        result_parts.append("Common JSON errors to check:")
        result_parts.append("  - Missing or extra commas")
        result_parts.append("  - Unclosed braces {} or brackets []")
        result_parts.append("  - Unescaped quotes in strings")
        result_parts.append("  - Trailing commas (not allowed in JSON)")
        result_parts.append("  - Single quotes instead of double quotes")
        result_parts.append("  - Unquoted property names")
        
        return "\n".join(result_parts)
    
    except Exception as e:
        return f"❌ Unexpected error during validation: {str(e)}"

