"""Middleware for providing filesystem tools to an agent."""
# ruff: noqa: E501

import os
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated, Literal, NotRequired

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain.tools import ToolRuntime
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.types import Command
from typing_extensions import TypedDict

from ..backends import StateBackend
from ..backends.protocol import BackendFactory, BackendProtocol, EditResult, WriteResult
from ..backends.utils import (
    format_content_with_line_numbers,
    format_grep_matches,
    sanitize_tool_call_id,
    truncate_if_too_long,
)

EMPTY_CONTENT_WARNING = "System reminder: File exists but has empty contents"
MAX_LINE_LENGTH = 2000
LINE_NUMBER_WIDTH = 6
DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 500
BACKEND_TYPES = BackendProtocol | BackendFactory


class FileData(TypedDict):
    """Data structure for storing file contents with metadata."""

    content: list[str]
    """Lines of the file."""

    created_at: str
    """ISO 8601 timestamp of file creation."""

    modified_at: str
    """ISO 8601 timestamp of last modification."""


def _file_data_reducer(left: dict[str, FileData] | None, right: dict[str, FileData | None]) -> dict[str, FileData]:
    """Merge file updates with support for deletions.

    This reducer enables file deletion by treating `None` values in the right
    dictionary as deletion markers. It's designed to work with LangGraph's
    state management where annotated reducers control how state updates merge.

    Args:
        left: Existing files dictionary. May be `None` during initialization.
        right: New files dictionary to merge. Files with `None` values are
            treated as deletion markers and removed from the result.

    Returns:
        Merged dictionary where right overwrites left for matching keys,
        and `None` values in right trigger deletions.

    Example:
        ```python
        existing = {"/file1.txt": FileData(...), "/file2.txt": FileData(...)}
        updates = {"/file2.txt": None, "/file3.txt": FileData(...)}
        result = file_data_reducer(existing, updates)
        # Result: {"/file1.txt": FileData(...), "/file3.txt": FileData(...)}
        ```
    """
    if left is None:
        return {k: v for k, v in right.items() if v is not None}

    result = {**left}
    for key, value in right.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = value
    return result


def _validate_path(path: str, *, allowed_prefixes: Sequence[str] | None = None) -> str:
    """Validate and normalize file path for security.

    Ensures paths are safe to use by preventing directory traversal attacks
    and enforcing consistent formatting. All paths are normalized to use
    forward slashes and start with a leading slash.

    Args:
        path: The path to validate and normalize.
        allowed_prefixes: Optional list of allowed path prefixes. If provided,
            the normalized path must start with one of these prefixes.

    Returns:
        Normalized canonical path starting with `/` and using forward slashes.

    Raises:
        ValueError: If path contains traversal sequences (`..` or `~`) or does
            not start with an allowed prefix when `allowed_prefixes` is specified.

    Example:
        ```python
        validate_path("foo/bar")  # Returns: "/foo/bar"
        validate_path("/./foo//bar")  # Returns: "/foo/bar"
        validate_path("../etc/passwd")  # Raises ValueError
        validate_path("/data/file.txt", allowed_prefixes=["/data/"])  # OK
        validate_path("/etc/file.txt", allowed_prefixes=["/data/"])  # Raises ValueError
        ```
    """
    if ".." in path or path.startswith("~"):
        msg = f"Path traversal not allowed: {path}"
        raise ValueError(msg)

    normalized = os.path.normpath(path)
    normalized = normalized.replace("\\", "/")

    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    if allowed_prefixes is not None and not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
        msg = f"Path must start with one of {allowed_prefixes}: {path}"
        raise ValueError(msg)

    return normalized


class FilesystemState(AgentState):
    """State for the filesystem middleware."""

    files: Annotated[NotRequired[dict[str, FileData]], _file_data_reducer]
    """Files in the filesystem."""


LIST_FILES_TOOL_DESCRIPTION = """Lists all files in the filesystem, filtering by directory.

Usage:
- The path parameter must be an absolute path, not a relative path
- The list_files tool will return a list of all files in the specified directory.
- This is very useful for exploring the file system and finding the right file to read or edit.
- You should almost ALWAYS use this tool before using the Read or Edit tools."""

READ_FILE_TOOL_DESCRIPTION = """Reads a file from the filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 500 lines starting from the beginning of the file
- **IMPORTANT for large files and codebase exploration**: Use pagination with offset and limit parameters to avoid context overflow
  - First scan: read_file(path, limit=100) to see file structure
  - Read more sections: read_file(path, offset=100, limit=200) for next 200 lines
  - Only omit limit (read full file) when necessary for editing
- Specify offset and limit: read_file(path, offset=0, limit=100) reads first 100 lines
- Any lines longer than 2000 characters will be truncated
- Results are returned using cat -n format, with line numbers starting at 1
- You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents.
- You should ALWAYS make sure a file has been read before editing it."""

EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance."""


WRITE_FILE_TOOL_DESCRIPTION = """Writes to a new file in the filesystem.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- The content parameter must be a string
- The write_file tool will create the a new file.
- Prefer to edit existing files over creating new ones when possible."""


GLOB_TOOL_DESCRIPTION = """Find files matching a glob pattern.

Usage:
- The glob tool finds files by matching patterns with wildcards
- Supports standard glob patterns: `*` (any characters), `**` (any directories), `?` (single character)
- Patterns can be absolute (starting with `/`) or relative
- Returns a list of absolute file paths that match the pattern

Examples:
- `**/*.py` - Find all Python files
- `*.txt` - Find all text files in root
- `/subdir/**/*.md` - Find all markdown files under /subdir"""

GREP_TOOL_DESCRIPTION = """Search for a pattern in files.

Usage:
- The grep tool searches for text patterns across files
- The pattern parameter is the text to search for (literal string, not regex)
- The path parameter filters which directory to search in (default is the current working directory)
- The glob parameter accepts a glob pattern to filter which files to search (e.g., `*.py`)
- The output_mode parameter controls the output format:
  - `files_with_matches`: List only file paths containing matches (default)
  - `content`: Show matching lines with file path and line numbers
  - `count`: Show count of matches per file

Examples:
- Search all files: `grep(pattern="TODO")`
- Search Python files only: `grep(pattern="import", glob="*.py")`
- Show matching lines: `grep(pattern="error", output_mode="content")`"""

FILESYSTEM_SYSTEM_PROMPT = """## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`

You have access to a filesystem which you can interact with using these tools.
All file paths must start with a /.

- ls: list files in a directory (requires absolute path)
- read_file: read a file from the filesystem
- write_file: write to a file in the filesystem
- edit_file: edit a file in the filesystem
- glob: find files matching a pattern (e.g., "**/*.py")
- grep: search for text within files"""


def _get_backend(backend: BACKEND_TYPES, runtime: ToolRuntime) -> BackendProtocol:
    """Get the resolved backend instance from backend or factory.

    Args:
        backend: Backend instance or factory function.
        runtime: The tool runtime context.

    Returns:
        Resolved backend instance.
    """
    if callable(backend):
        return backend(runtime)
    return backend


def _ls_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the ls (list files) tool.

    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.

    Returns:
        Configured ls tool that lists files using the backend.
    """
    tool_description = custom_description or LIST_FILES_TOOL_DESCRIPTION

    @tool(description=tool_description)
    def ls(runtime: ToolRuntime[None, FilesystemState], path: str) -> list[str]:
        resolved_backend = _get_backend(backend, runtime)
        validated_path = _validate_path(path)
        infos = resolved_backend.ls_info(validated_path)
        return [fi.get("path", "") for fi in infos]

    return ls


def _read_file_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the read_file tool.

    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.

    Returns:
        Configured read_file tool that reads files using the backend.
    """
    tool_description = custom_description or READ_FILE_TOOL_DESCRIPTION

    @tool(description=tool_description)
    def read_file(
        file_path: str,
        runtime: ToolRuntime[None, FilesystemState],
        offset: int = DEFAULT_READ_OFFSET,
        limit: int = DEFAULT_READ_LIMIT,
    ) -> str:
        resolved_backend = _get_backend(backend, runtime)
        file_path = _validate_path(file_path)
        return resolved_backend.read(file_path, offset=offset, limit=limit)

    return read_file


def _write_file_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the write_file tool.

    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.

    Returns:
        Configured write_file tool that creates new files using the backend.
    """
    tool_description = custom_description or WRITE_FILE_TOOL_DESCRIPTION

    @tool(description=tool_description)
    def write_file(
        file_path: str,
        content: str,
        runtime: ToolRuntime[None, FilesystemState],
    ) -> Command | str:
        resolved_backend = _get_backend(backend, runtime)
        file_path = _validate_path(file_path)
        res: WriteResult = resolved_backend.write(file_path, content)
        if res.error:
            return res.error
        # If backend returns state update, wrap into Command with ToolMessage
        if res.files_update is not None:
            return Command(
                update={
                    "files": res.files_update,
                    "messages": [
                        ToolMessage(
                            content=f"Updated file {res.path}",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )
        return f"Updated file {res.path}"

    return write_file


def _edit_file_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the edit_file tool.

    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.

    Returns:
        Configured edit_file tool that performs string replacements in files using the backend.
    """
    tool_description = custom_description or EDIT_FILE_TOOL_DESCRIPTION

    @tool(description=tool_description)
    def edit_file(
        file_path: str,
        old_string: str,
        new_string: str,
        runtime: ToolRuntime[None, FilesystemState],
        *,
        replace_all: bool = False,
    ) -> Command | str:
        resolved_backend = _get_backend(backend, runtime)
        file_path = _validate_path(file_path)
        res: EditResult = resolved_backend.edit(file_path, old_string, new_string, replace_all=replace_all)
        if res.error:
            return res.error
        if res.files_update is not None:
            return Command(
                update={
                    "files": res.files_update,
                    "messages": [
                        ToolMessage(
                            content=f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )
        return f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'"

    return edit_file


def _glob_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the glob tool.

    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.

    Returns:
        Configured glob tool that finds files by pattern using the backend.
    """
    tool_description = custom_description or GLOB_TOOL_DESCRIPTION

    @tool(description=tool_description)
    def glob(pattern: str, runtime: ToolRuntime[None, FilesystemState], path: str = "/") -> list[str]:
        resolved_backend = _get_backend(backend, runtime)
        infos = resolved_backend.glob_info(pattern, path=path)
        return [fi.get("path", "") for fi in infos]

    return glob


def _grep_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the grep tool.

    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.

    Returns:
        Configured grep tool that searches for patterns in files using the backend.
    """
    tool_description = custom_description or GREP_TOOL_DESCRIPTION

    @tool(description=tool_description)
    def grep(
        pattern: str,
        runtime: ToolRuntime[None, FilesystemState],
        path: str | None = None,
        glob: str | None = None,
        output_mode: Literal["files_with_matches", "content", "count"] = "files_with_matches",
    ) -> str:
        resolved_backend = _get_backend(backend, runtime)
        raw = resolved_backend.grep_raw(pattern, path=path, glob=glob)
        if isinstance(raw, str):
            return raw
        formatted = format_grep_matches(raw, output_mode)
        return truncate_if_too_long(formatted)  # type: ignore[arg-type]

    return grep


def _validate_json_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the validate_json tool.
    
    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.
    
    Returns:
        Configured validate_json tool that validates JSON from files or strings using the backend.
    """
    from typing import Optional
    
    tool_description = custom_description or """Validate JSON syntax and structure.
    
    Use this tool to verify that a JSON string or file is valid.
    You can provide either:
    - file_path: Path to a JSON file to read and validate (e.g., "/plan_outline.json")
    - json_string: Direct JSON string to validate
    
    If both are provided, file_path takes precedence (the file will be read and validated).
    """
    
    @tool(description=tool_description)
    def validate_json(
        runtime: ToolRuntime[None, FilesystemState],
        json_string: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> str:
        """Validate JSON syntax and structure."""
        import json
        
        result_parts = []
        json_content = ""
        
        # Determine the source of JSON content
        if file_path:
            # Read from file using the backend
            try:
                resolved_backend = _get_backend(backend, runtime)
                validated_path = _validate_path(file_path)
                formatted_content = resolved_backend.read(validated_path, offset=0, limit=100000)  # Read full file
                
                # Strip line numbers from formatted content (format: "     1\t{...}")
                # The filesystem backend returns content with line numbers like: "     1\t{...}"
                # Line numbers are right-aligned in 6-char field, followed by tab
                # Pattern: optional spaces, then digits (possibly with decimal like "5.1"), then tab
                import re
                lines = formatted_content.split('\n')
                json_lines = []
                # Regex to match line number prefix: optional spaces, then number (int or decimal), then tab
                line_number_pattern = re.compile(r'^\s*\d+(\.\d+)?\t')
                for line in lines:
                    # Check if line starts with line number format
                    if line_number_pattern.match(line):
                        # Remove the line number prefix (everything up to and including the tab)
                        content = line_number_pattern.sub('', line)
                        json_lines.append(content)
                    else:
                        # No line number prefix, use line as-is
                        json_lines.append(line)
                
                json_content = '\n'.join(json_lines)
                result_parts.append(f"📄 Reading JSON from file: {file_path}")
                result_parts.append("")
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
    
    return validate_json


def _aggregate_document_tool_generator(
    backend: BackendProtocol | Callable[[ToolRuntime], BackendProtocol],
    custom_description: str | None = None,
) -> BaseTool:
    """Generate the aggregate_document tool that uses the filesystem backend.
    
    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_description: Optional custom description for the tool.
    
    Returns:
        Configured aggregate_document tool that reads and writes files using the backend.
    """
    tool_description = custom_description or """Concatenate multiple section files (already written) into a final document.

    Args:
        sections: List of objects describing each section to aggregate. Every entry must include:
            - section_number (int): order in the final document
            - file (str): absolute path to the section file (e.g., "/section_section_1.md")
        Optional keys:
            - title (str): human friendly heading to insert before the section
        output_file: Path where the final document should be written (e.g., "/final_research_document.md").
        generate_table_of_contents: Whether to prepend a basic table of contents (default: True).

    Returns:
        bool: True if aggregation succeeded. Raises ValueError on failure.
    
    CRITICAL: This tool uses the LangGraph filesystem backend. All file paths must be absolute paths starting with "/".
    The tool will read section files from the backend and write the aggregated document to the backend.
    """
    
    @tool(description=tool_description)
    def aggregate_document(
        sections: list[dict],
        output_file: str,
        runtime: ToolRuntime[None, FilesystemState],
        generate_table_of_contents: bool = True,
    ) -> str | Command:
        """Concatenate multiple section files into a final document using the filesystem backend."""
        from typing import Any
        
        if not sections:
            raise ValueError("No sections provided to aggregate_document.")
        
        resolved_backend = _get_backend(backend, runtime)
        
        normalized_sections: list[dict[str, Any]] = []
        for idx, entry in enumerate(sections):
            if not isinstance(entry, dict):
                raise ValueError(f"Section #{idx} is not an object: {entry!r}")
            if "section_number" not in entry or "file" not in entry:
                raise ValueError(
                    f"Section #{idx} missing required keys. "
                    "Each section must include 'section_number' and 'file'."
                )
            try:
                number = int(entry["section_number"])
            except (TypeError, ValueError):
                raise ValueError(
                    f"Section #{idx} has non-integer section_number: {entry['section_number']!r}"
                ) from None
            file_path = _validate_path(entry["file"])
            title = entry.get("title") or f"Section {number}"
            normalized_sections.append(
                {
                    "section_number": number,
                    "file": file_path,
                    "title": title,
                }
            )
        
        normalized_sections.sort(key=lambda s: s["section_number"])
        
        aggregated_chunks: list[str] = []
        toc_lines: list[str] = []
        
        for section in normalized_sections:
            file_path: str = section["file"]
            # Try to read the file using the backend
            try:
                # Read full file content (use large limit to get entire file)
                content = resolved_backend.read(file_path, offset=0, limit=1000000)
                
                # Strip line numbers from content (backend formats with line numbers)
                import re
                lines = content.split('\n')
                content_lines = []
                line_number_pattern = re.compile(r'^\s*\d+(\.\d+)?\t')
                for line in lines:
                    if line_number_pattern.match(line):
                        content = line_number_pattern.sub('', line)
                        content_lines.append(content)
                    else:
                        content_lines.append(line)
                
                content = '\n'.join(content_lines).strip()
                
            except Exception as e:
                raise ValueError(f"Section file not found or cannot be read: {file_path}. Error: {str(e)}")
            
            title = section["title"]
            aggregated_chunks.append(f"## {title}\n\n{content}\n\n")
            
            if generate_table_of_contents:
                # Simple slugify for anchor
                anchor = "".join(ch.lower() if ch.isalnum() else "-" for ch in title)
                while "--" in anchor:
                    anchor = anchor.replace("--", "-")
                anchor = anchor.strip("-") or f"section-{section['section_number']}"
                toc_lines.append(f"{section['section_number']}. [{title}](#{anchor})")
        
        final_parts: list[str] = []
        if generate_table_of_contents and toc_lines:
            final_parts.append("# Table of Contents\n")
            final_parts.extend(line + "\n" for line in toc_lines)
            final_parts.append("\n")
        
        final_parts.extend(aggregated_chunks)
        final_content = "".join(final_parts)
        
        # Write output file using the backend
        output_path = _validate_path(output_file)
        write_result = resolved_backend.write(output_path, final_content)
        
        if write_result.error:
            raise ValueError(f"Failed to write output file {output_path}: {write_result.error}")
        
        # Return Command with state update if backend provides it
        if write_result.files_update is not None:
            return Command(
                update={
                    "files": write_result.files_update,
                    "messages": [
                        ToolMessage(
                            content=f"Successfully aggregated {len(sections)} sections into {output_path}",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )
        
        return f"Successfully aggregated {len(sections)} sections into {output_path}"
    
    return aggregate_document


TOOL_GENERATORS = {
    "ls": _ls_tool_generator,
    "read_file": _read_file_tool_generator,
    "write_file": _write_file_tool_generator,
    "edit_file": _edit_file_tool_generator,
    "glob": _glob_tool_generator,
    "grep": _grep_tool_generator,
    "validate_json": _validate_json_tool_generator,
    "aggregate_document": _aggregate_document_tool_generator,
}


def _get_filesystem_tools(
    backend: BackendProtocol,
    custom_tool_descriptions: dict[str, str] | None = None,
) -> list[BaseTool]:
    """Get filesystem tools.

    Args:
        backend: Backend to use for file storage, or a factory function that takes runtime and returns a backend.
        custom_tool_descriptions: Optional custom descriptions for tools.

    Returns:
        List of configured filesystem tools (ls, read_file, write_file, edit_file, glob, grep).
    """
    if custom_tool_descriptions is None:
        custom_tool_descriptions = {}
    tools = []
    for tool_name, tool_generator in TOOL_GENERATORS.items():
        tool = tool_generator(backend, custom_tool_descriptions.get(tool_name))
        tools.append(tool)
    return tools


TOO_LARGE_TOOL_MSG = """Tool result too large, the result of this tool call {tool_call_id} was saved in the filesystem at this path: {file_path}
You can read the result from the filesystem by using the read_file tool, but make sure to only read part of the result at a time.
You can do this by specifying an offset and limit in the read_file tool call.
For example, to read the first 100 lines, you can use the read_file tool with offset=0 and limit=100.

Here are the first 10 lines of the result:
{content_sample}
"""


class FilesystemMiddleware(AgentMiddleware):
    """Middleware for providing filesystem tools to an agent.

    This middleware adds six filesystem tools to the agent: ls, read_file, write_file,
    edit_file, glob, and grep. Files can be stored using any backend that implements
    the BackendProtocol.

    Args:
        backend: Backend for file storage. If not provided, defaults to StateBackend
            (ephemeral storage in agent state). For persistent storage or hybrid setups,
            use CompositeBackend with custom routes.
        system_prompt: Optional custom system prompt override.
        custom_tool_descriptions: Optional custom tool descriptions override.
        tool_token_limit_before_evict: Optional token limit before evicting a tool result to the filesystem.

    Example:
        ```python
        from deepagents.middleware.filesystem import FilesystemMiddleware
        from deepagents.memory.backends import StateBackend, StoreBackend, CompositeBackend
        from langchain.agents import create_agent

        # Ephemeral storage only (default)
        agent = create_agent(middleware=[FilesystemMiddleware()])

        # With hybrid storage (ephemeral + persistent /memories/)
        backend = CompositeBackend(default=StateBackend(), routes={"/memories/": StoreBackend()})
        agent = create_agent(middleware=[FilesystemMiddleware(memory_backend=backend)])
        ```
    """

    state_schema = FilesystemState

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES | None = None,
        system_prompt: str | None = None,
        custom_tool_descriptions: dict[str, str] | None = None,
        tool_token_limit_before_evict: int | None = 20000,
    ) -> None:
        """Initialize the filesystem middleware.

        Args:
            backend: Backend for file storage, or a factory callable. Defaults to StateBackend if not provided.
            system_prompt: Optional custom system prompt override.
            custom_tool_descriptions: Optional custom tool descriptions override.
            tool_token_limit_before_evict: Optional token limit before evicting a tool result to the filesystem.
        """
        self.tool_token_limit_before_evict = tool_token_limit_before_evict

        # Use provided backend or default to StateBackend factory
        self.backend = backend if backend is not None else (lambda rt: StateBackend(rt))

        # Set system prompt (allow full override)
        self.system_prompt = system_prompt if system_prompt is not None else FILESYSTEM_SYSTEM_PROMPT

        self.tools = _get_filesystem_tools(self.backend, custom_tool_descriptions)

    def _get_backend(self, runtime: ToolRuntime) -> BackendProtocol:
        """Get the resolved backend instance from backend or factory.

        Args:
            runtime: The tool runtime context.

        Returns:
            Resolved backend instance.
        """
        if callable(self.backend):
            return self.backend(runtime)
        return self.backend

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Update the system prompt to include instructions on using the filesystem.

        Args:
            request: The model request being processed.
            handler: The handler function to call with the modified request.

        Returns:
            The model response from the handler.
        """
        if self.system_prompt is not None:
            request.system_prompt = request.system_prompt + "\n\n" + self.system_prompt if request.system_prompt else self.system_prompt
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """(async) Update the system prompt to include instructions on using the filesystem.

        Args:
            request: The model request being processed.
            handler: The handler function to call with the modified request.

        Returns:
            The model response from the handler.
        """
        if self.system_prompt is not None:
            request.system_prompt = request.system_prompt + "\n\n" + self.system_prompt if request.system_prompt else self.system_prompt
        return await handler(request)

    def _process_large_message(
        self,
        message: ToolMessage,
        resolved_backend: BackendProtocol,
    ) -> tuple[ToolMessage, dict[str, FileData] | None]:
        content = message.content
        if not isinstance(content, str) or len(content) <= 4 * self.tool_token_limit_before_evict:
            return message, None

        sanitized_id = sanitize_tool_call_id(message.tool_call_id)
        file_path = f"/large_tool_results/{sanitized_id}"
        result = resolved_backend.write(file_path, content)
        if result.error:
            return message, None
        content_sample = format_content_with_line_numbers([line[:1000] for line in content.splitlines()[:10]], start_line=1)
        processed_message = ToolMessage(
            TOO_LARGE_TOOL_MSG.format(
                tool_call_id=message.tool_call_id,
                file_path=file_path,
                content_sample=content_sample,
            ),
            tool_call_id=message.tool_call_id,
        )
        return processed_message, result.files_update

    def _intercept_large_tool_result(self, tool_result: ToolMessage | Command, runtime: ToolRuntime) -> ToolMessage | Command:
        if isinstance(tool_result, ToolMessage) and isinstance(tool_result.content, str):
            if not (self.tool_token_limit_before_evict and len(tool_result.content) > 4 * self.tool_token_limit_before_evict):
                return tool_result
            resolved_backend = self._get_backend(runtime)
            processed_message, files_update = self._process_large_message(
                tool_result,
                resolved_backend,
            )
            return (
                Command(
                    update={
                        "files": files_update,
                        "messages": [processed_message],
                    }
                )
                if files_update is not None
                else processed_message
            )

        if isinstance(tool_result, Command):
            update = tool_result.update
            if update is None:
                return tool_result
            command_messages = update.get("messages", [])
            accumulated_file_updates = dict(update.get("files", {}))
            resolved_backend = self._get_backend(runtime)
            processed_messages = []
            for message in command_messages:
                if not (
                    self.tool_token_limit_before_evict
                    and isinstance(message, ToolMessage)
                    and isinstance(message.content, str)
                    and len(message.content) > 4 * self.tool_token_limit_before_evict
                ):
                    processed_messages.append(message)
                    continue
                processed_message, files_update = self._process_large_message(
                    message,
                    resolved_backend,
                )
                processed_messages.append(processed_message)
                if files_update is not None:
                    accumulated_file_updates.update(files_update)
            return Command(update={**update, "messages": processed_messages, "files": accumulated_file_updates})

        return tool_result

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Check the size of the tool call result and evict to filesystem if too large.

        Args:
            request: The tool call request being processed.
            handler: The handler function to call with the modified request.

        Returns:
            The raw ToolMessage, or a pseudo tool message with the ToolResult in state.
        """
        if self.tool_token_limit_before_evict is None or request.tool_call["name"] in TOOL_GENERATORS:
            return handler(request)

        tool_result = handler(request)
        return self._intercept_large_tool_result(tool_result, request.runtime)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """(async)Check the size of the tool call result and evict to filesystem if too large.

        Args:
            request: The tool call request being processed.
            handler: The handler function to call with the modified request.

        Returns:
            The raw ToolMessage, or a pseudo tool message with the ToolResult in state.
        """
        if self.tool_token_limit_before_evict is None or request.tool_call["name"] in TOOL_GENERATORS:
            return await handler(request)

        tool_result = await handler(request)
        return self._intercept_large_tool_result(tool_result, request.runtime)
