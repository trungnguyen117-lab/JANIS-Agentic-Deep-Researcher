"""Document aggregation tool for combining completed section files."""

from pathlib import Path
from typing import Any, List

from langchain_core.tools import tool


def _slugify(text: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-")


@tool
def aggregate_document(
    sections: List[dict],
    output_file: str,
    generate_table_of_contents: bool = True,
) -> bool:
    """Concatenate multiple section files (already written) into a final document.

    Args:
        sections: List of objects describing each section to aggregate. Every entry
            must include:
              - `section_number` (int): order in the final document
              - `file` (str): absolute or workspace-relative path to the section file
            Optional keys:
              - `title` (str): human friendly heading to insert before the section
        output_file: Path where the final document should be written.
        generate_table_of_contents: Whether to prepend a basic table of contents that
            uses provided titles (if available).

    Returns:
        bool: True if aggregation succeeded. Raises ValueError on failure.
    """

    if not sections:
        raise ValueError("No sections provided to aggregate_document.")

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
        file_path = Path(entry["file"]).expanduser()
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
        file_path: Path = section["file"]
        if not file_path.is_file():
            raise ValueError(f"Section file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        title = section["title"]

        aggregated_chunks.append(f"## {title}\n\n{content.strip()}\n\n")

        if generate_table_of_contents:
            anchor = _slugify(title) or f"section-{section['section_number']}"
            toc_lines.append(f"{section['section_number']}. [{title}](#{anchor})")

    final_parts: list[str] = []
    if generate_table_of_contents and toc_lines:
        final_parts.append("# Table of Contents\n")
        final_parts.extend(line + "\n" for line in toc_lines)
        final_parts.append("\n")

    final_parts.extend(aggregated_chunks)

    output_path = Path(output_file).expanduser()
    output_path.write_text("".join(final_parts), encoding="utf-8")

    return True

