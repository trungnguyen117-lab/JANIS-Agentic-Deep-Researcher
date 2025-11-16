"""Document aggregation tool for combining sections into final research document."""

import json
import re
from typing import List, Dict, Optional
from langchain_core.tools import tool


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug for markdown anchors."""
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def generate_table_of_contents(sections: List[Dict]) -> str:
    """Generate a markdown table of contents from sections."""
    toc_lines = ["# Table of Contents", ""]
    
    for i, section in enumerate(sections, 1):
        title = section.get("title", f"Section {i}")
        section_id = section.get("id", f"section_{i}")
        # Create anchor from title
        anchor = slugify(title)
        toc_lines.append(f"{i}. [{title}](#{anchor})")
    
    return "\n".join(toc_lines) + "\n\n"


def normalize_citations(content: str, citation_style: str = "numeric") -> str:
    """Normalize citations in content.
    
    Args:
        content: The text content with citations
        citation_style: "numeric" (keep [1], [2]) or "markdown" (convert to [@key])
    
    Returns:
        Content with normalized citations
    """
    if citation_style == "numeric":
        # Keep numeric citations but ensure they're consistent
        # Find all numeric citations like [1], [2], [1,2], etc.
        # For now, just return as-is since we're preserving content
        return content
    elif citation_style == "markdown":
        # Convert numeric citations to markdown style
        # Pattern: [1] or [1,2,3] -> [@ref1] or [@ref1; @ref2; @ref3]
        def replace_citation(match):
            numbers = match.group(1)
            # Split by comma and convert each number
            refs = [f"@ref{num.strip()}" for num in numbers.split(',')]
            return f"[{'; '.join(refs)}]"
        
        # Replace [1], [2], [1,2,3] patterns
        content = re.sub(r'\[(\d+(?:,\s*\d+)*)\]', replace_citation, content)
        return content
    else:
        return content


@tool
def aggregate_document(
    outline_file: str = "/plan_outline.json",
    output_file: str = "/final_research_document.md",
    citation_style: str = "numeric"
) -> str:
    """Aggregate sections into final research document using pure file operations (NO LLM).
    
    This tool reads section files in order, concatenates them, and generates a table of contents.
    It does NOT rewrite or modify section content - it preserves each section exactly as written.
    
    Args:
        outline_file: Path to the plan outline JSON file (default: "/plan_outline.json")
        output_file: Path where the final document will be saved (default: "/final_research_document.md")
        citation_style: Citation style - "numeric" (keep [1], [2]) or "markdown" (convert to [@key])
    
    Returns:
        Success message with details about the aggregated document
    
    Example:
        aggregate_document(
            outline_file="/plan_outline.json",
            output_file="/final_research_document.md",
            citation_style="numeric"
        )
    """
    import os
    
    result_parts = []
    
    # Step 1: Read outline to get section order
    try:
        with open(outline_file, 'r', encoding='utf-8') as f:
            outline_data = json.load(f)
    except FileNotFoundError:
        return f"❌ ERROR: Outline file not found: {outline_file}"
    except json.JSONDecodeError as e:
        return f"❌ ERROR: Invalid JSON in outline file: {str(e)}"
    except Exception as e:
        return f"❌ ERROR: Could not read outline file: {str(e)}"
    
    if "sections" not in outline_data:
        return "❌ ERROR: Outline file missing 'sections' array"
    
    sections = outline_data["sections"]
    if not sections:
        return "❌ ERROR: Outline file has no sections"
    
    # Sort sections by order
    sections = sorted(sections, key=lambda s: s.get("order", 0))
    
    result_parts.append(f"📋 Found {len(sections)} sections in outline")
    
    # Step 2: Generate table of contents
    toc = generate_table_of_contents(sections)
    result_parts.append("✅ Generated table of contents")
    
    # Step 3: Read all section files in order
    aggregated_content = []
    aggregated_content.append(toc)
    
    missing_files = []
    section_stats = []
    
    for section in sections:
        section_id = section.get("id", "")
        section_title = section.get("title", "Untitled Section")
        section_file = f"/section_{section_id}.md"
        
        # Check if file exists
        if not os.path.exists(section_file):
            missing_files.append(section_file)
            result_parts.append(f"⚠️ WARNING: Section file not found: {section_file}")
            continue
        
        try:
            with open(section_file, 'r', encoding='utf-8') as f:
                section_content = f.read()
            
            # Normalize citations if needed
            if citation_style != "numeric":
                section_content = normalize_citations(section_content, citation_style)
            
            # Count words for stats
            word_count = len(re.findall(r'\b\w+\b', section_content))
            section_stats.append({
                "title": section_title,
                "file": section_file,
                "words": word_count
            })
            
            # Append section content
            aggregated_content.append(f"## {section_title}\n\n")
            aggregated_content.append(section_content)
            aggregated_content.append("\n\n")  # Blank line between sections
            
        except Exception as e:
            result_parts.append(f"❌ ERROR: Could not read section file {section_file}: {str(e)}")
            missing_files.append(section_file)
    
    if missing_files:
        return f"❌ ERROR: Missing section files: {', '.join(missing_files)}. Cannot aggregate document."
    
    # Step 4: Combine all content
    final_content = "".join(aggregated_content)
    
    # Step 5: Save final document
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_content)
    except Exception as e:
        return f"❌ ERROR: Could not write final document to {output_file}: {str(e)}"
    
    # Step 6: Generate summary
    total_words = sum(stat["words"] for stat in section_stats)
    estimated_pages = total_words / 500.0
    
    result_parts.append("")
    result_parts.append("✅ Document aggregation complete!")
    result_parts.append("")
    result_parts.append("📊 Document Statistics:")
    result_parts.append(f"   - Total sections: {len(sections)}")
    result_parts.append(f"   - Total words: {total_words:,}")
    result_parts.append(f"   - Estimated pages: {estimated_pages:.1f}")
    result_parts.append("")
    result_parts.append("📄 Section Details:")
    for stat in section_stats:
        result_parts.append(f"   - {stat['title']}: {stat['words']:,} words")
    result_parts.append("")
    result_parts.append(f"💾 Final document saved to: {output_file}")
    result_parts.append(f"📝 Citation style: {citation_style}")
    result_parts.append("")
    result_parts.append("✅ All sections preserved exactly as written (no LLM rewriting)")
    
    return "\n".join(result_parts)

