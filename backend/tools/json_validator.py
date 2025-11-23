"""JSON validation tool for verifying JSON syntax and structure."""

import json
from typing import Dict, Any, Optional
from langchain_core.tools import tool


@tool
def validate_json(json_string: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Validate JSON syntax and structure.
    
    Use this tool to verify that a JSON string or file is valid.
    This is especially important for plan_outline.json which must be valid JSON for the frontend to parse.
    
    You can provide either:
    - `file_path`: Path to a JSON file to read and validate (e.g., "/plan_outline.json")
    - `json_string`: Direct JSON string to validate
    
    If both are provided, `file_path` takes precedence (the file will be read and validated).
    
    Args:
        json_string: Optional JSON string to validate directly. If not provided, file_path must be provided.
        file_path: Optional path to a JSON file to read and validate. If provided, the file will be read automatically.
    
    Returns:
        A detailed validation result message indicating:
        - Whether the JSON is valid
        - If invalid, the specific error and location (line, column, problematic line)
        - If valid, confirmation and basic structure information (sections count, required fields)
    
    Examples:
        # Validate a file directly (recommended for large files)
        validate_json(file_path="/plan_outline.json")
        
        # Validate a JSON string directly
        validate_json(json_string='{"sections": [{"id": "section_1"}]}')
    """
    result_parts = []
    json_content = ""
    
    # Determine the source of JSON content
    if file_path:
        # Read from file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json_content = f.read()
            result_parts.append(f"📄 Reading JSON from file: {file_path}")
            result_parts.append("")
        except FileNotFoundError:
            return f"❌ ERROR: File not found: {file_path}"
        except Exception as e:
            return f"❌ ERROR: Could not read file {file_path}: {str(e)}"
    elif json_string:
        # Use provided JSON string
        json_content = json_string
        result_parts.append("📄 Validating provided JSON string")
        result_parts.append("")
    else:
        return "❌ ERROR: Either 'json_string' or 'file_path' must be provided."
    
    # Validate the JSON content
    if not json_content or not json_content.strip():
        return "❌ ERROR: JSON content is empty or contains only whitespace. Please provide valid JSON."
    
    try:
        # Parse the JSON to check syntax
        parsed = json.loads(json_content)
        
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
        if e.lineno and json_content:
            lines = json_content.split('\n')
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

