"""Text counting tool for counting words and characters in text files or strings."""

from typing import Optional
from langchain_core.tools import tool


@tool
def count_text(file_path: Optional[str] = None, text_content: Optional[str] = None) -> str:
    """Count words and characters in a text file or text content.
    
    Use this tool to verify if a section matches the `estimatedDepth` specified in the outline.
    For example, if `estimatedDepth` is "2-3 pages" (approximately 1000-1500 words), you can count
    the words in the section to verify it matches.
    
    You can provide either:
    - `file_path`: Path to a file to read and count (e.g., "/section_section_1.md")
    - `text_content`: Direct text content to count
    
    If both are provided, `file_path` takes precedence.
    
    Args:
        file_path: Optional path to a file to read and count. Use read_file() first if you need the content.
        text_content: Optional text content to count directly.
    
    Returns:
        A detailed count report including:
        - Total characters (including spaces)
        - Total characters (excluding spaces)
        - Total words
        - Total lines
        - Estimated pages (assuming ~500 words per page)
        - Word count range (e.g., "1000-1500 words" for 2-3 pages)
    
    Examples:
        # Count words in a file
        count_text(file_path="/section_section_1.md")
        
        # Count words in text content
        count_text(text_content="# Section Title\n\nThis is some text...")
        
        # Count after reading file
        content = read_file("/section_section_1.md")
        count_text(text_content=content)
    """
    import re
    
    # Get the text to count
    text = ""
    
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            return f"❌ ERROR: File not found: {file_path}"
        except Exception as e:
            return f"❌ ERROR: Could not read file {file_path}: {str(e)}"
    elif text_content:
        text = text_content
    else:
        return "❌ ERROR: Either 'file_path' or 'text_content' must be provided."
    
    if not text:
        return "⚠️ WARNING: Text is empty. Counts are all zero."
    
    # Count characters
    total_chars_with_spaces = len(text)
    total_chars_without_spaces = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))
    
    # Count words (split by whitespace and filter empty strings)
    words = re.findall(r'\b\w+\b', text)
    total_words = len(words)
    
    # Count lines
    total_lines = len(text.splitlines())
    non_empty_lines = len([line for line in text.splitlines() if line.strip()])
    
    # Estimate pages (assuming ~500 words per page, ~2500 characters per page)
    estimated_pages_by_words = total_words / 500.0
    estimated_pages_by_chars = total_chars_with_spaces / 2500.0
    estimated_pages = (estimated_pages_by_words + estimated_pages_by_chars) / 2.0
    
    # Word count ranges for common page estimates
    def get_word_range(pages):
        """Convert page estimate to word range."""
        if pages < 1:
            return f"~{int(pages * 500)} words"
        elif pages < 2:
            return "~500-1000 words (1-2 pages)"
        elif pages < 3:
            return "~1000-1500 words (2-3 pages)"
        elif pages < 4:
            return "~1500-2000 words (3-4 pages)"
        elif pages < 5:
            return "~2000-2500 words (4-5 pages)"
        else:
            return f"~{int(pages * 500)} words ({pages:.1f} pages)"
    
    word_range = get_word_range(estimated_pages)
    
    # Build result
    result_parts = []
    result_parts.append("📊 Text Count Report")
    result_parts.append("=" * 50)
    result_parts.append("")
    result_parts.append(f"📝 Characters (with spaces): {total_chars_with_spaces:,}")
    result_parts.append(f"📝 Characters (without spaces): {total_chars_without_spaces:,}")
    result_parts.append(f"📝 Words: {total_words:,}")
    result_parts.append(f"📝 Lines: {total_lines:,} (non-empty: {non_empty_lines:,})")
    result_parts.append("")
    result_parts.append(f"📄 Estimated Length: {estimated_pages:.2f} pages")
    result_parts.append(f"📄 Word Range: {word_range}")
    result_parts.append("")
    result_parts.append("💡 Note: Page estimates assume ~500 words per page")
    result_parts.append("💡 To verify against outline:")
    result_parts.append("   - If outline says '2-3 pages', section should be ~1000-1500 words")
    result_parts.append("   - If outline says '4-5 pages', section should be ~2000-2500 words")
    result_parts.append("   - Compare the word count above with the `estimatedDepth` in `/plan_outline.json`")
    
    return "\n".join(result_parts)

