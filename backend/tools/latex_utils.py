"""LaTeX utilities for report generation and compilation.

Inspired by AgentLaboratory's LaTeX compilation functionality.
"""

import subprocess
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional


def compile_latex_to_pdf(
    latex_code: str,
    output_dir: Optional[str] = None,
    compile_pdf: bool = True,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Compile LaTeX code to PDF.
    
    Inspired by AgentLaboratory's compile_latex function.
    
    Args:
        latex_code: LaTeX source code to compile
        output_dir: Directory to save output files (optional, uses temp dir if not provided)
        compile_pdf: Whether to actually compile to PDF (if False, just validates)
        timeout: Timeout for compilation in seconds
    
    Returns:
        Dictionary with:
        - success: bool - Whether compilation was successful
        - message: str - Success or error message
        - pdf_path: Optional[str] - Path to generated PDF (if successful and compile_pdf=True)
        - tex_path: Optional[str] - Path to .tex file
    """
    # Add necessary LaTeX packages (inspired by AgentLaboratory)
    required_packages = [
        "\\usepackage{amsmath}",
        "\\usepackage{amssymb}",
        "\\usepackage{graphicx}",
        "\\usepackage{hyperref}",
        "\\usepackage{url}",
        "\\usepackage{xcolor}",
        "\\usepackage{booktabs}",
        "\\usepackage{enumitem}",
    ]
    
    # Check if documentclass exists, if not add it
    if "\\documentclass" not in latex_code:
        latex_code = "\\documentclass{article}\n" + latex_code
    
    # Add packages if not already present
    for package in required_packages:
        package_name = package.split("{")[1].split("}")[0]
        if f"\\usepackage{{{package_name}}}" not in latex_code and package not in latex_code:
            # Insert after documentclass
            if "\\documentclass" in latex_code:
                lines = latex_code.split("\n")
                docclass_idx = next((i for i, line in enumerate(lines) if "\\documentclass" in line), 0)
                lines.insert(docclass_idx + 1, package)
                latex_code = "\n".join(lines)
            else:
                latex_code = package + "\n" + latex_code
    
    # Create output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="latex_compile_")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    tex_file_path = os.path.join(output_dir, "report.tex")
    
    # Write LaTeX code to file
    try:
        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(latex_code)
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to write LaTeX file: {str(e)}",
            "pdf_path": None,
            "tex_path": tex_file_path,
        }
    
    if not compile_pdf:
        return {
            "success": True,
            "message": "LaTeX code written successfully (compilation skipped)",
            "pdf_path": None,
            "tex_path": tex_file_path,
        }
    
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
            "message": "pdflatex is not available. LaTeX code saved but not compiled.",
            "pdf_path": None,
            "tex_path": tex_file_path,
        }
    
    # Compile LaTeX to PDF
    try:
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "report.tex"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            cwd=output_dir,
        )
        
        pdf_path = os.path.join(output_dir, "report.pdf")
        if os.path.exists(pdf_path):
            return {
                "success": True,
                "message": "LaTeX compiled successfully to PDF",
                "pdf_path": pdf_path,
                "tex_path": tex_file_path,
            }
        else:
            return {
                "success": False,
                "message": "Compilation completed but PDF not found",
                "pdf_path": None,
                "tex_path": tex_file_path,
            }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"LaTeX compilation timed out after {timeout} seconds",
            "pdf_path": None,
            "tex_path": tex_file_path,
        }
    
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode("utf-8") if e.stderr else "Unknown error"
        return {
            "success": False,
            "message": f"LaTeX compilation failed: {error_output[:500]}",
            "pdf_path": None,
            "tex_path": tex_file_path,
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error during LaTeX compilation: {str(e)}",
            "pdf_path": None,
            "tex_path": tex_file_path,
        }


def markdown_to_latex(markdown_content: str) -> str:
    """Convert Markdown content to LaTeX format.
    
    This is a basic converter. For more complex conversions, consider using pandoc.
    
    Args:
        markdown_content: Markdown content to convert
    
    Returns:
        LaTeX code (without documentclass and packages, just the content)
    """
    latex = markdown_content
    
    # Convert headers
    latex = latex.replace("# ", "\\section{")
    latex = latex.replace("## ", "\\subsection{")
    latex = latex.replace("### ", "\\subsubsection{")
    
    # Close section headers (simple approach - assumes headers are on their own line)
    import re
    latex = re.sub(r"(\\section\{[^}]+)", r"\1}", latex)
    latex = re.sub(r"(\\subsection\{[^}]+)", r"\1}", latex)
    latex = re.sub(r"(\\subsubsection\{[^}]+)", r"\1}", latex)
    
    # Convert bold
    latex = latex.replace("**", "\\textbf{")
    # Close bold (simple approach)
    latex = re.sub(r"(\\textbf\{[^}]+)", r"\1}", latex)
    
    # Convert italic
    latex = latex.replace("*", "\\textit{")
    # This is more complex, so we'll use a simpler approach
    latex = latex.replace("\\textit{", "*")
    latex = re.sub(r"\*([^*]+)\*", r"\\textit{\1}", latex)
    
    # Convert code blocks
    latex = latex.replace("```", "\\begin{verbatim}")
    latex = latex.replace("```", "\\end{verbatim}")
    
    # Convert inline code
    latex = re.sub(r"`([^`]+)`", r"\\texttt{\1}", latex)
    
    # Convert lists (basic)
    lines = latex.split("\n")
    result_lines = []
    in_list = False
    
    for line in lines:
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            if not in_list:
                result_lines.append("\\begin{itemize}")
                in_list = True
            item_text = line.strip()[2:].strip()
            result_lines.append(f"\\item {item_text}")
        elif line.strip().startswith(("1. ", "2. ", "3. ", "4. ", "5. ")):
            if not in_list:
                result_lines.append("\\begin{enumerate}")
                in_list = True
            item_text = re.sub(r"^\d+\.\s*", "", line.strip())
            result_lines.append(f"\\item {item_text}")
        else:
            if in_list:
                result_lines.append("\\end{itemize}")
                in_list = False
            result_lines.append(line)
    
    if in_list:
        result_lines.append("\\end{itemize}")
    
    latex = "\n".join(result_lines)
    
    return latex

