"""
FastAPI application for outline agent.

This provides a production-aligned alternative to `langgraph dev` that:
- Avoids CLI dependency conflicts
- Works with LangGraph Studio (point baseUrl to this server)
- Provides full control over the server configuration

The graph is automatically mounted by langgraph-api when this app is specified
in langgraph.json under http.app. The langgraph dev command will use this app
and automatically add all LangGraph API routes.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import os

# Create FastAPI app
# The graph will be automatically mounted by langgraph-api based on langgraph.json
app = FastAPI(
    title="Outline Agent API",
    description="Simple outline agent for creating and fixing paper outlines. Denario handles paper generation.",
    version="0.1.0",
)

# Get project root directory (parent of backend)
PROJECT_ROOT = Path(__file__).parent.parent
PAPER_DIR = PROJECT_ROOT / "project" / "paper"


@app.get("/api/paper/latex")
async def get_latex_file():
    """Serve the final LaTeX file (paper_v4_final.tex)."""
    latex_path = PAPER_DIR / "paper_v4_final.tex"
    if not latex_path.exists():
        raise HTTPException(status_code=404, detail="LaTeX file not found. Paper may not be generated yet.")
    return FileResponse(
        latex_path,
        media_type="text/plain",
        filename="paper_v4_final.tex",
        headers={"Content-Disposition": 'attachment; filename="paper_v4_final.tex"'}
    )


@app.get("/api/paper/pdf")
async def get_pdf_file():
    """Serve the final PDF file (paper_v4_final.pdf)."""
    pdf_path = PAPER_DIR / "paper_v4_final.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found. Paper may not be generated yet or xelatex compilation failed.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="paper_v4_final.pdf",
        headers={"Content-Disposition": 'inline; filename="paper_v4_final.pdf"'}
    )


@app.get("/api/paper/convert-to-pdf")
async def convert_latex_to_pdf():
    """Convert LaTeX file to PDF using xelatex."""
    import subprocess
    import asyncio
    
    latex_path = PAPER_DIR / "paper_v4_final.tex"
    if not latex_path.exists():
        raise HTTPException(status_code=404, detail="LaTeX file not found. Paper may not be generated yet.")
    
    # Check if xelatex is available
    try:
        result = subprocess.run(["which", "xelatex"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(
                status_code=503,
                detail="xelatex is not installed. Please install it with: sudo apt-get install texlive-xetex texlive-latex-extra"
            )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="xelatex is not installed. Please install it with: sudo apt-get install texlive-xetex texlive-latex-extra"
        )
    
    # Run xelatex compilation in a thread to avoid blocking
    def compile_pdf():
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-file-line-error", "paper_v4_final.tex"],
            cwd=str(PAPER_DIR),
            input="\n",
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        if result.returncode != 0:
            raise RuntimeError(f"PDF compilation failed: {result.stderr}")
        return result
    
    try:
        await asyncio.to_thread(compile_pdf)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="PDF compilation timed out")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF compilation error: {str(e)}")
    
    # Return the generated PDF
    pdf_path = PAPER_DIR / "paper_v4_final.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="PDF compilation completed but file not found")
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="paper_v4_final.pdf",
        headers={"Content-Disposition": 'inline; filename="paper_v4_final.pdf"'}
    )


@app.get("/api/paper/status")
async def get_paper_status():
    """Get status of generated paper files."""
    latex_path = PAPER_DIR / "paper_v4_final.tex"
    pdf_path = PAPER_DIR / "paper_v4_final.pdf"
    
    return {
        "latex_exists": latex_path.exists(),
        "pdf_exists": pdf_path.exists(),
        "latex_path": str(latex_path) if latex_path.exists() else None,
        "pdf_path": str(pdf_path) if pdf_path.exists() else None,
    }

# Optional: Add custom routes here if needed
# The LangGraph API routes (assistants, threads, runs, etc.) are automatically
# added by langgraph-api based on the graphs defined in langgraph.json

