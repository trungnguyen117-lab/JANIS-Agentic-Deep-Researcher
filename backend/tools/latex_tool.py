"""LaTeX tool for generating and compiling LaTeX reports.

Inspired by AgentLaboratory's LaTeX compilation functionality.
"""

from typing import Dict, Any
import subprocess
import os
import tempfile


def generate_latex_report(
    markdown_content: str,
    title: str = "Research Report",
    author: str = "Research Agent",
    compile_pdf: bool = False,
) -> Dict[str, Any]:
    """Generate LaTeX report from markdown content.
    
    Inspired by AgentLaboratory's LaTeX generation and compilation.
    
    Args:
        markdown_content: Markdown content to convert to LaTeX
        title: Report title
        author: Report author
        compile_pdf: Whether to compile to PDF (requires pdflatex)
    
    Returns:
        Dictionary with:
        - latex_code: str - Generated LaTeX code
        - success: bool - Whether generation/compilation was successful
        - message: str - Success or error message
        - pdf_path: Optional[str] - Path to PDF if compiled successfully
    """
    # Convert markdown to LaTeX (basic conversion)
    latex_content = _markdown_to_latex_content(markdown_content)
    
    # Build complete LaTeX document
    latex_code = _build_latex_document(latex_content, title, author)
    
    result = {
        "latex_code": latex_code,
        "success": True,
        "message": "LaTeX code generated successfully",
        "pdf_path": None,
    }
    
    # Optionally compile to PDF
    if compile_pdf:
        compile_result = _compile_latex(latex_code)
        result.update(compile_result)
    
    return result


def _markdown_to_latex_content(markdown: str) -> str:
    """Convert markdown content to LaTeX content (without document structure)."""
    latex = markdown
    
    # Convert headers
    import re
    latex = re.sub(r"^### (.*)$", r"\\subsubsection{\1}", latex, flags=re.MULTILINE)
    latex = re.sub(r"^## (.*)$", r"\\subsection{\1}", latex, flags=re.MULTILINE)
    latex = re.sub(r"^# (.*)$", r"\\section{\1}", latex, flags=re.MULTILINE)
    
    # Convert bold
    latex = re.sub(r"\*\*(.*?)\*\*", r"\\textbf{\1}", latex)
    latex = re.sub(r"__(.*?)__", r"\\textbf{\1}", latex)
    
    # Convert italic (but not bold markers)
    # Need to be careful not to match **
    latex = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\\textit{\1}", latex)
    latex = re.sub(r"(?<!_)_([^_]+?)_(?!_)", r"\\textit{\1}", latex)
    
    # Convert code blocks
    latex = re.sub(
        r"```[\s\S]*?```",
        lambda m: f"\\begin{{verbatim}}\n{m.group(0)[3:-3]}\n\\end{{verbatim}}",
        latex,
    )
    
    # Convert inline code
    latex = re.sub(r"`([^`]+)`", r"\\texttt{\1}", latex)
    
    # Convert links
    latex = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\\href{\2}{\1}", latex)
    
    # Convert lists
    lines = latex.split("\n")
    result_lines = []
    in_itemize = False
    in_enumerate = False
    
    for line in lines:
        stripped = line.strip()
        
        # Unordered list
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_itemize and not in_enumerate:
                result_lines.append("\\begin{itemize}")
                in_itemize = True
            item_text = stripped[2:].strip()
            result_lines.append(f"\\item {item_text}")
        # Ordered list
        elif re.match(r"^\d+\.\s+", stripped):
            if in_itemize:
                result_lines.append("\\end{itemize}")
                in_itemize = False
            if not in_enumerate:
                result_lines.append("\\begin{enumerate}")
                in_enumerate = True
            item_text = re.sub(r"^\d+\.\s+", "", stripped)
            result_lines.append(f"\\item {item_text}")
        else:
            if in_itemize:
                result_lines.append("\\end{itemize}")
                in_itemize = False
            if in_enumerate:
                result_lines.append("\\end{enumerate}")
                in_enumerate = False
            result_lines.append(line)
    
    if in_itemize:
        result_lines.append("\\end{itemize}")
    if in_enumerate:
        result_lines.append("\\end{enumerate}")
    
    return "\n".join(result_lines)


def _build_latex_document(content: str, title: str, author: str) -> str:
    """Build complete LaTeX document with packages and structure.
    
    Inspired by AgentLaboratory's LaTeX package setup.
    """
    # Required packages (inspired by AgentLaboratory)
    packages = [
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage{amsmath}",
        "\\usepackage{amssymb}",
        "\\usepackage{graphicx}",
        "\\usepackage{hyperref}",
        "\\usepackage{url}",
        "\\usepackage{xcolor}",
        "\\usepackage{booktabs}",
        "\\usepackage{enumitem}",
        "\\usepackage{verbatim}",
    ]
    
    latex = "\\documentclass{article}\n"
    latex += "\n".join(packages) + "\n"
    latex += "\n\\title{" + title + "}\n"
    latex += "\\author{" + author + "}\n"
    latex += "\\date{\\today}\n"
    latex += "\n\\begin{document}\n"
    latex += "\\maketitle\n\n"
    latex += content
    latex += "\n\n\\end{document}\n"
    
    return latex


def _compile_latex(latex_code: str, timeout: int = 30) -> Dict[str, Any]:
    """Compile LaTeX code to PDF.
    
    Inspired by AgentLaboratory's compile_latex function.
    """
    # Check if pdflatex is available
    try:
        subprocess.run(
            ["pdflatex", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return {
            "success": False,
            "message": "pdflatex is not available. LaTeX code generated but not compiled.",
            "pdf_path": None,
        }
    
    # Create temp directory for compilation
    with tempfile.TemporaryDirectory(prefix="latex_compile_") as temp_dir:
        tex_file = os.path.join(temp_dir, "report.tex")
        
        # Write LaTeX code
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(latex_code)
        
        # Compile
        try:
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "report.tex"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                cwd=temp_dir,
            )
            
            pdf_file = os.path.join(temp_dir, "report.pdf")
            if os.path.exists(pdf_file):
                # Read PDF content
                with open(pdf_file, "rb") as f:
                    pdf_content = f.read()
                
                return {
                    "success": True,
                    "message": "LaTeX compiled successfully to PDF",
                    "pdf_path": None,  # PDF content is in pdf_content, but we can't return file path
                    "pdf_content": pdf_content,  # Binary PDF content
                }
            else:
                return {
                    "success": False,
                    "message": "Compilation completed but PDF not found",
                    "pdf_path": None,
                }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": f"LaTeX compilation timed out after {timeout} seconds",
                "pdf_path": None,
            }
        
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.decode("utf-8") if e.stderr else "Unknown error"
            return {
                "success": False,
                "message": f"LaTeX compilation failed: {error_output[:500]}",
                "pdf_path": None,
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error during LaTeX compilation: {str(e)}",
                "pdf_path": None,
            }

