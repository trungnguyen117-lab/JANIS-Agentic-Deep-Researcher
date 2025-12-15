"""Tool for generating papers using Denario workflow."""

import asyncio
import json
import logging
import queue
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


def extract_thread_id_from_config(config: Any) -> str | None:
    """Extract thread_id from LangGraph RunnableConfig.
    
    Tries multiple methods to extract thread_id from the config object.
    Returns None if not found.
    """
    if not config:
        return None
    
    thread_id = None
    
    # Method 1: Check config.configurable (dict-like access)
    if hasattr(config, 'configurable'):
        configurable = config.configurable
        if isinstance(configurable, dict):
            thread_id = configurable.get('thread_id')
        elif hasattr(configurable, 'get'):
            thread_id = configurable.get('thread_id')
        # Also try direct attribute access
        if not thread_id and hasattr(configurable, 'thread_id'):
            thread_id = configurable.thread_id
        # Try dict-like access with __getitem__
        if not thread_id:
            try:
                if hasattr(configurable, '__getitem__'):
                    thread_id = configurable['thread_id']
            except (KeyError, TypeError):
                pass
    
    # Method 2: Check if config is a dict-like object
    if not thread_id and hasattr(config, 'get'):
        try:
            configurable = config.get('configurable', {})
            if isinstance(configurable, dict):
                thread_id = configurable.get('thread_id')
        except Exception:
            pass
    
    # Method 3: Check config directly (some LangGraph versions store it here)
    if not thread_id and hasattr(config, 'thread_id'):
        thread_id = config.thread_id
    
    # Method 4: Try accessing as attributes
    if not thread_id:
        try:
            if hasattr(config, '__dict__'):
                thread_id = config.__dict__.get('thread_id')
        except Exception:
            pass
    
    return thread_id

# Add backend/src to path for Denario imports
import sys
from pathlib import Path as PathLib

_backend_src = PathLib(__file__).parent.parent.parent.parent / "src"
if str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

# Use project directory relative to backend folder
# Default to ./project/plan_outline.json (relative to project root)
# Resolve to absolute path to avoid issues with working directory
_PROJECT_ROOT = PathLib(__file__).resolve().parent.parent.parent.parent.parent  # Go up to project root
OUTLINE_FILE_PATH = str(_PROJECT_ROOT / "project" / "plan_outline.json")


def sync_generate_paper_from_outline(
    project_dir: str | None = None,
    paper_name: str = "generated_paper",
    config: Any | None = None,
) -> str:
    """Generate a scientific paper using Denario workflow from the outline.
    
    This tool reads plan_outline.json from the project directory and passes it
    directly to Denario class to generate the paper.
    
    Args:
        project_dir: Directory where the paper will be generated (default: "./project")
        paper_name: Name for the generated paper (default: "generated_paper")
        config: RunnableConfig from LangGraph (contains thread_id)
    
    Returns:
        str: Success message with path to generated paper, or error message
    """
    try:
        # Try to get config from parameter or from execution context
        if not config:
            try:
                from langchain_core.runnables import get_config
                config = get_config()
                logger.debug(f"Got config from get_config(): {type(config)}")
            except Exception as e:
                logger.debug(f"Could not get config from get_config(): {e}")
        
        # Extract thread_id using helper function
        thread_id = extract_thread_id_from_config(config)
        
        # Debug logging
        if thread_id:
            logger.info(f"✅ Extracted thread_id: {thread_id}")
            print(f"[Denario] ✅ Extracted thread_id: {thread_id}", flush=True)
        else:
            logger.warning(f"⚠️ Could not extract thread_id from config. Config type: {type(config)}")
            print(f"[Denario] ⚠️ Could not extract thread_id. Config type: {type(config)}", flush=True)
            if config:
                logger.debug(f"Config attributes: {dir(config)}")
                if hasattr(config, 'configurable'):
                    logger.debug(f"Config.configurable: {config.configurable}, type: {type(config.configurable)}")
                    try:
                        if isinstance(config.configurable, dict):
                            logger.debug(f"Config.configurable keys: {list(config.configurable.keys())}")
                            print(f"[Denario] Config.configurable keys: {list(config.configurable.keys())}", flush=True)
                        elif hasattr(config.configurable, '__dict__'):
                            logger.debug(f"Config.configurable.__dict__: {config.configurable.__dict__}")
                            print(f"[Denario] Config.configurable.__dict__: {config.configurable.__dict__}", flush=True)
                    except Exception as e:
                        logger.debug(f"Error inspecting config.configurable: {e}")
                        print(f"[Denario] Error inspecting config.configurable: {e}", flush=True)
        
        # Use thread-based directory - REQUIRED, no fallbacks
        if project_dir is None or project_dir == "/":
            if thread_id:
                project_dir = str(_PROJECT_ROOT / "project" / "threads" / str(thread_id))
                # Ensure thread directory exists
                Path(project_dir).mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Using thread-specific directory: {project_dir}")
                print(f"[Denario] ✅ Thread ID: {thread_id} - Using isolated directory: {project_dir}", flush=True)
            else:
                error_msg = "❌ No thread_id found in config. Thread-based file storage is required. Cannot proceed without thread_id."
                logger.error(error_msg)
                print(f"[Denario] {error_msg}", flush=True)
                raise ValueError(error_msg)
        
        # Load the outline from thread-specific directory ONLY (no fallbacks)
        outline_path = Path(project_dir).resolve() / "plan_outline.json"
        
        if not outline_path.exists():
            error_msg = f"Outline file not found in thread directory: {outline_path}. Please create an outline first using the outline-agent for this thread."
            logger.error(error_msg, exc_info=True)
            raise FileNotFoundError(error_msg)
        
        logger.info(f"Loading outline from {outline_path}")
        
        # Check file size first - if it's 0 or very small, it might be empty or being written
        file_size = outline_path.stat().st_size
        logger.info(f"Outline file size: {file_size} bytes")
        
        if file_size == 0:
            raise ValueError(f"Outline file is empty (0 bytes): {outline_path}. The file may be being written. Please wait a moment and try again.")
        
        # Read and parse JSON with better error handling
        # Retry once if file seems to be in the middle of being written
        import time
        max_retries = 2
        for attempt in range(max_retries):
            try:
                with outline_path.open("r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        if attempt < max_retries - 1:
                            logger.warning(f"File appears empty, waiting 0.5s and retrying... (attempt {attempt + 1}/{max_retries})")
                            time.sleep(0.5)
                            continue
                        raise ValueError(f"Outline file is empty: {outline_path}")
                    outline = json.loads(content)
                    break  # Success, exit retry loop
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"JSON decode error, waiting 0.5s and retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(0.5)
                    continue
                logger.error(f"JSON decode error at {outline_path}: {e}")
                logger.error(f"File size: {outline_path.stat().st_size} bytes")
                # Try to read first few lines for debugging
                try:
                    with outline_path.open("r", encoding="utf-8") as f:
                        first_lines = "".join(f.readlines()[:5])
                        logger.error(f"First 5 lines of file: {first_lines}")
                except Exception:
                    pass
                raise ValueError(f"Invalid JSON in outline file {outline_path}: {e}")
        
        # Validate basic structure
        if not isinstance(outline, dict) or 'sections' not in outline:
            raise ValueError("Invalid outline format: missing 'sections' key")
        
        if not isinstance(outline['sections'], list) or len(outline['sections']) == 0:
            raise ValueError("Invalid outline format: 'sections' must be a non-empty list")
        
        logger.info(f"Outline loaded successfully with {len(outline.get('sections', []))} sections")
        
        # Import and run Denario in a thread to avoid blocking during import
        # The import chain (cmbagent -> autogen -> jsonschema) has blocking filesystem calls
        logger.info("Starting paper generation with Denario...")
        print("[Denario] 🚀 Starting paper generation workflow...", flush=True)
        
        def _generate_theoretical_results(den, outline, project_dir):
            """Generate theoretical results without code execution."""
            from langchain_openai import ChatOpenAI
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_anthropic import ChatAnthropic
            from pathlib import Path as PathLib
            from src.lib.denario.config import INPUT_FILES, IDEA_FILE, METHOD_FILE, RESULTS_FILE
            
            # Read idea and methods
            idea_file = PathLib(project_dir) / INPUT_FILES / IDEA_FILE
            method_file = PathLib(project_dir) / INPUT_FILES / METHOD_FILE
            
            idea_content = ""
            method_content = ""
            
            if idea_file.exists():
                with idea_file.open("r", encoding="utf-8") as f:
                    idea_content = f.read()
            
            if method_file.exists():
                with method_file.open("r", encoding="utf-8") as f:
                    method_content = f.read()
            
            # Determine LLM based on available keys
            llm = None
            if den.keys.OPENAI:
                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.7,
                    openai_api_key=den.keys.OPENAI
                )
            elif den.keys.GEMINI:
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    temperature=0.7,
                    google_api_key=den.keys.GEMINI
                )
            elif den.keys.ANTHROPIC:
                llm = ChatAnthropic(
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.7,
                    anthropic_api_key=den.keys.ANTHROPIC
                )
            else:
                raise ValueError("No API keys available for theoretical results generation")
            
            # Get results section description from outline
            results_section = next(
                (s for s in outline.get('sections', []) 
                 if s.get('id') == 'results' or 'result' in s.get('title', '').lower()),
                None
            )
            results_guidance = ""
            if results_section:
                results_guidance = f"\n\nFocus on: {results_section.get('description', '')}"
                if results_section.get('subsections'):
                    results_guidance += "\n\nSubsections to cover:\n"
                    for sub in results_section['subsections']:
                        if isinstance(sub, dict):
                            results_guidance += f"- {sub.get('title', '')}: {sub.get('description', '')}\n"
                        else:
                            results_guidance += f"- {sub}\n"
            
            # Generate theoretical results
            prompt = f"""Based on the research idea and methodology below, generate theoretical results and findings.

IMPORTANT: This is a theoretical research paper. Do NOT generate code, do NOT suggest running experiments, do NOT install packages.
Focus on:
- Theoretical analysis and findings
- Literature-based comparisons
- Expected outcomes based on existing research
- Theoretical performance metrics
- Conceptual insights and implications
{results_guidance}

Research Idea:
{idea_content}

Methodology:
{method_content}

Provide the results in a clear, concise manner, suitable for a scientific paper's results section.
"""
            print("[Denario] 🧠 Generating theoretical results with LLM...", flush=True)
            response = llm.invoke(prompt)
            theoretical_results = response.content if hasattr(response, 'content') else str(response)
            
            # Write theoretical results to file
            results_path = PathLib(project_dir) / INPUT_FILES / RESULTS_FILE
            results_path.parent.mkdir(parents=True, exist_ok=True)
            with results_path.open("w", encoding="utf-8") as f:
                f.write(theoretical_results)
            print("[Denario] ✅ Theoretical results saved.", flush=True)
            
            den.research.results = theoretical_results
            den.research.plot_paths = []  # No plots in theoretical mode
        
        def _generate_paper():
            """Run Denario paper generation in a thread to avoid blocking imports."""
            try:
                # Import Denario inside the thread to avoid blocking the event loop
                # This import triggers cmbagent -> autogen -> jsonschema which has blocking calls
                from src.lib.denario.denario import Denario
                from src.lib.denario.paper_agents.journal import Journal
                from src.lib.denario.config import INPUT_FILES, IDEA_FILE, METHOD_FILE, RESULTS_FILE
                
                # Initialize Denario with project directory
                den = Denario(project_dir=project_dir)
                
                # Set data description from outline before running research phase
                # Combine all section descriptions into a single data description
                combined_description = "Research topic based on outline:\n\n"
                for section in outline.get('sections', []):
                    combined_description += f"## {section.get('title', 'Section')}\n"
                    combined_description += f"{section.get('description', '')}\n\n"
                    if section.get('subsections'):
                        for sub in section['subsections']:
                            if isinstance(sub, dict):
                                combined_description += f"- {sub.get('title', '')}: {sub.get('description', '')}\n"
                
                # This creates the data_description.md file that the research workflow expects
                den.set_data_description(data_description=combined_description)
                logger.info("Data description set from outline")
                print("[Denario] 📋 Data description created from outline", flush=True)
                
                # Always run the research phase before generating the paper
                # The research files (idea.md, methods.md, results.md) don't exist yet,
                # so we need to generate them through the research workflow
                logger.info("Running research phase (idea, method, results)...")
                print("[Denario] 🔬 Starting research phase...", flush=True)
                
                # Step 1: Generate research idea based on data description
                print("[Denario] 📝 Generating research idea...", flush=True)
                # Use Denario's original default model configuration for stability
                den.get_idea(mode="fast")
                logger.info("Research idea generated")
                
                # Step 2: Generate methodology to test the idea
                print("[Denario] 🔬 Generating methodology...", flush=True)
                # Use Denario's original default model configuration for stability
                den.get_method(mode="fast")
                logger.info("Methodology generated")
                
                # Step 3: Generate results (theoretical or experimental)
                # Default: run experiments to unlock plots/figures, but keep them lightweight.
                # Skip experiments only if the outline explicitly indicates theoretical-only,
                # or if DENARIO_FORCE_THEORETICAL=true is set.
                outline_text = json.dumps(outline, indent=2).lower()

                # Theoretical-only indicators (skip experiments if present)
                theoretical_indicators = [
                    "theoretical", "literature-based", "literature review", "conceptual",
                    "no code", "no implementation", "theoretical analysis", "theoretical study",
                    "literature analysis", "survey", "review paper", "literature survey"
                ]
                has_theoretical_indicator = any(indicator in outline_text for indicator in theoretical_indicators)

                # Run experiments unless forced theoretical.
                requires_experiments = not has_theoretical_indicator

                # Environment override
                import os
                force_theoretical = os.getenv("DENARIO_FORCE_THEORETICAL", "false").lower() == "true"

                # Lightweight constraints to keep experiments cheap and quick
                lightweight_constraints = (
                    "Lightweight only: no package installation; no internet fetch; "
                    "prefer built-ins; small synthetic data; keep runtime under 3 minutes; "
                    "avoid heavy training/large downloads; CPU-friendly."
                )

                if requires_experiments and not force_theoretical:
                    logger.info("🧪 Running experiments in lightweight mode (constraints applied)")
                    print("[Denario] 🧪 Running experiments (lightweight: no installs, small synthetic data, <3min)...", flush=True)
                    # Try experiments up to 2 times; on persistent failure, fall back to theoretical mode
                    experiments_succeeded = False
                    last_error = None
                    for attempt in range(2):
                        try:
                            logger.info(f"Attempt {attempt+1}/2 for experimental results")
                            den.get_results(
                                hardware_constraints=lightweight_constraints,
                                max_n_attempts=3,
                                max_n_steps=3,
                            )
                            experiments_succeeded = True
                            logger.info("Results generated via experiments")
                            break
                        except Exception as exp_err:
                            last_error = exp_err
                            logger.warning(f"Experiment attempt {attempt+1} failed: {exp_err}")
                    if not experiments_succeeded:
                        logger.warning(
                            f"All experimental attempts failed (last error: {last_error}). "
                            "Falling back to theoretical results."
                        )
                        print("[Denario] ⚠️ Experiments failed; falling back to theoretical results.", flush=True)
                        _generate_theoretical_results(den, outline, project_dir)
                        logger.info("Theoretical results generated after experiment failure")
                else:
                    if force_theoretical and requires_experiments:
                        logger.info("⚠️ Code execution requested but DENARIO_FORCE_THEORETICAL=true - using theoretical mode")
                        print("[Denario] ⚠️ Code execution disabled by DENARIO_FORCE_THEORETICAL - using theoretical mode", flush=True)
                    else:
                        logger.info("✅ Using theoretical mode (no code execution) - outline does not explicitly require code execution")
                        print("[Denario] ✅ Using theoretical research mode (no code execution, no package installation)", flush=True)
                    
                    # Generate theoretical results only (no code execution)
                    print("[Denario] 📚 Generating theoretical results (no code execution)...", flush=True)
                    _generate_theoretical_results(den, outline, project_dir)
                    logger.info("Theoretical results generated")
                
                print("[Denario] ✅ Research phase completed", flush=True)
                
                # Step 4: Generate paper from research results
                # The outline guides the structure, but content comes from actual research
                print("[Denario] 📄 Generating paper from research results...", flush=True)
                # Use Denario's internal default models for paper writing
                den.get_paper(
                    journal=Journal.NONE,
                    writer="scientist",
                    cmbagent_keywords=False,
                    add_citations=True,
                    outline=outline,  # Pass outline directly to Denario (guides structure)
                )
            except Exception as e:
                # Log full traceback for debugging
                import traceback
                full_traceback = traceback.format_exc()
                logger.error(f"Error inside Denario.get_paper: {e}\nFull traceback:\n{full_traceback}", exc_info=True)
                print(f"[Denario] ❌ Error in paper generation:\n{full_traceback}", flush=True)
                raise RuntimeError(f"Denario paper generation failed: {str(e)}\n\nTraceback:\n{full_traceback}") from e
        
        # Run in thread to avoid blocking filesystem operations during import
        # Use concurrent.futures for sync context
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            executor.submit(_generate_paper).result()
        
        logger.info("Paper generation completed successfully")
        
        # Check if paper was generated (Denario saves it to paper folder)
        paper_path = Path(project_dir) / "paper"
        pdf_file = paper_path / "paper_v4_final.pdf"
        
        pdf_exists = pdf_file.exists()
        
        # Find all LaTeX files in the paper directory
        latex_files = list(paper_path.glob("*.tex")) if paper_path.exists() else []
        
        if latex_files:
            message = f"✅ Paper '{paper_name}' generated successfully!\n\n"
            message += f"📄 Found {len(latex_files)} LaTeX file(s) in paper directory\n"
            message += f"🔗 Download LaTeX: /api/paper/latex\n"
            
            if pdf_exists:
                message += f"📕 PDF file: paper/paper_v4_final.pdf\n"
                message += f"🔗 View PDF: /api/paper/pdf\n"
            else:
                message += f"⚠️ PDF not generated (xelatex may not be installed)\n"
                message += f"🔗 Convert to PDF: /api/paper/convert-to-pdf\n"
            
            # Return message with special marker to indicate paper files should be added to state
            # The graph.py tools_node will extract this and add files to state
            # We'll read all LaTeX files in tools_node to avoid embedding large content in message
            message += f"\n\nPAPER_FILES_START\n"
            # Just list the files - tools_node will read them from disk
            for latex_file in sorted(latex_files):
                relative_path = latex_file.relative_to(paper_path.parent)
                message += f"{relative_path}:<READ_FROM_DISK>\n"
            if pdf_exists:
                message += f"paper/paper_v4_final.pdf:[PDF file - download via /api/paper/pdf]\n"
            message += f"PAPER_FILES_END\n"
            
            return message
        else:
            return f"✅ Paper generation workflow completed. Check {paper_path} for generated files."
            
    except FileNotFoundError as e:
        # Check if it's about xelatex (LaTeX compiler not installed)
        error_str = str(e)
        if "xelatex" in error_str.lower():
            # LaTeX files were generated, but PDF compilation failed due to missing xelatex
            paper_path = Path(project_dir) / "paper"
            latex_files_exist = paper_path.exists() and any(paper_path.rglob("*.tex"))
            if latex_files_exist:
                error_msg = f"⚠️ LaTeX files generated successfully, but PDF compilation failed because 'xelatex' is not installed.\n\nTo install xelatex:\n  sudo apt-get install texlive-xetex texlive-latex-extra\n\nLaTeX source files are available at: {paper_path}"
            else:
                error_msg = f"❌ PDF compilation failed: xelatex not found. Install with: sudo apt-get install texlive-xetex"
            logger.warning(error_msg)
            return error_msg
        elif "plan_outline.json" in error_str or "outline" in error_str.lower():
            error_msg = f"❌ Outline file not found. Please create an outline first using the outline-agent. Expected location: {project_dir}/plan_outline.json"
        else:
            error_msg = f"❌ File not found: {error_str}"
        logger.error(f"{error_msg} (Original error: {e})", exc_info=True)
        return error_msg
    except (ValueError, json.JSONDecodeError) as e:
        error_msg = f"❌ Invalid outline format: {e}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        error_msg = f"❌ Error generating paper: {str(e)}"
        logger.error(f"{error_msg}\nFull traceback:\n{full_traceback}", exc_info=True)
        print(f"[Denario] {error_msg}", flush=True)
        print(f"[Denario] Full traceback:\n{full_traceback}", flush=True)
        # Include traceback in return message for debugging
        return f"{error_msg}\n\nTraceback:\n{full_traceback}"


async def async_generate_paper_from_outline(
    project_dir: str | None = None,
    paper_name: str = "generated_paper",
    config: Any | None = None,
) -> str:
    """Async version of generate_paper_from_outline.
    
    Reads outline from project directory and passes it directly to Denario.
    """
    # Initialize writer to None at the start to avoid UnboundLocalError
    writer = None
    try:
        # Try to get config from parameter or from execution context
        if not config:
            try:
                from langchain_core.runnables import get_config
                config = get_config()
                logger.debug(f"Got config from get_config(): {type(config)}")
            except Exception as e:
                logger.debug(f"Could not get config from get_config(): {e}")
        
        # Extract thread_id using helper function
        thread_id = extract_thread_id_from_config(config)
        
        # Debug logging
        if thread_id:
            logger.info(f"✅ Extracted thread_id: {thread_id}")
            print(f"[Denario] ✅ Extracted thread_id: {thread_id}", flush=True)
        else:
            logger.warning(f"⚠️ Could not extract thread_id from config. Config type: {type(config)}")
            print(f"[Denario] ⚠️ Could not extract thread_id. Config type: {type(config)}", flush=True)
            if config:
                logger.debug(f"Config attributes: {dir(config)}")
                if hasattr(config, 'configurable'):
                    logger.debug(f"Config.configurable: {config.configurable}, type: {type(config.configurable)}")
                    try:
                        if isinstance(config.configurable, dict):
                            logger.debug(f"Config.configurable keys: {list(config.configurable.keys())}")
                            print(f"[Denario] Config.configurable keys: {list(config.configurable.keys())}", flush=True)
                        elif hasattr(config.configurable, '__dict__'):
                            logger.debug(f"Config.configurable.__dict__: {config.configurable.__dict__}")
                            print(f"[Denario] Config.configurable.__dict__: {config.configurable.__dict__}", flush=True)
                    except Exception as e:
                        logger.debug(f"Error inspecting config.configurable: {e}")
                        print(f"[Denario] Error inspecting config.configurable: {e}", flush=True)
        
        # Use thread-based directory - REQUIRED, no fallbacks
        if project_dir is None or project_dir == "/":
            if thread_id:
                project_dir = str(_PROJECT_ROOT / "project" / "threads" / str(thread_id))
                # Ensure thread directory exists
                await asyncio.to_thread(Path(project_dir).mkdir, parents=True, exist_ok=True)
                logger.info(f"✅ Using thread-specific directory: {project_dir}")
                print(f"[Denario] ✅ Thread ID: {thread_id} - Using isolated directory: {project_dir}", flush=True)
            else:
                error_msg = "❌ No thread_id found in config. Thread-based file storage is required. Cannot proceed without thread_id."
                logger.error(error_msg)
                print(f"[Denario] {error_msg}", flush=True)
                raise ValueError(error_msg)
        
        # Load the outline from thread-specific directory ONLY (no fallbacks)
        outline_path = Path(project_dir).resolve() / "plan_outline.json"
        
        outline_exists = await asyncio.to_thread(outline_path.exists)
        logger.info(f"Looking for outline file in thread directory: {outline_path} (exists: {outline_exists})")
        
        if not outline_exists:
            error_msg = f"Outline file not found in thread directory: {outline_path}. Please create an outline first using the outline-agent for this thread."
            logger.error(error_msg, exc_info=True)
            raise FileNotFoundError(error_msg)
        
        logger.info(f"Loading outline from {outline_path}")
        
        # Check file size first - if it's 0 or very small, it might be empty or being written
        file_size = await asyncio.to_thread(lambda: outline_path.stat().st_size)
        logger.info(f"Outline file size: {file_size} bytes")
        
        if file_size == 0:
            raise ValueError(f"Outline file is empty (0 bytes): {outline_path}. The file may be being written. Please wait a moment and try again.")
        
        # Read file in thread to avoid blocking with better error handling and retry
        import time
        max_retries = 2
        
        def _read_file():
            for attempt in range(max_retries):
                try:
                    with outline_path.open("r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if not content:
                            if attempt < max_retries - 1:
                                logger.warning(f"File appears empty, waiting 0.5s and retrying... (attempt {attempt + 1}/{max_retries})")
                                time.sleep(0.5)
                                continue
                            raise ValueError(f"Outline file is empty: {outline_path}")
                        return json.loads(content)
                except json.JSONDecodeError as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"JSON decode error, waiting 0.5s and retrying... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(0.5)
                        continue
                    logger.error(f"JSON decode error at {outline_path}: {e}")
                    logger.error(f"File size: {outline_path.stat().st_size} bytes")
                    # Try to read first few lines for debugging
                    try:
                        with outline_path.open("r", encoding="utf-8") as f:
                            first_lines = "".join(f.readlines()[:5])
                            logger.error(f"First 5 lines of file: {first_lines}")
                    except Exception:
                        pass
                    raise ValueError(f"Invalid JSON in outline file {outline_path}: {e}")
        
        outline = await asyncio.to_thread(_read_file)
        
        if not isinstance(outline, dict) or 'sections' not in outline:
            raise ValueError("Invalid outline format: missing 'sections' key")
        
        if not isinstance(outline['sections'], list) or len(outline['sections']) == 0:
            raise ValueError("Invalid outline format: 'sections' must be a non-empty list")
        
        logger.info(f"Outline loaded successfully with {len(outline.get('sections', []))} sections")
        
        # Use get_stream_writer for progress updates if available
        from langgraph.config import get_stream_writer
        try:
            writer = get_stream_writer()
            if writer:
                print("[Denario] ✅ Stream writer initialized", flush=True)
        except Exception as e:
            logger.warning(f"Could not get stream writer: {e}")
            writer = None
            print(f"[Denario] ⚠️ Stream writer not available: {e}", flush=True)
        
        # Import and run Denario in a thread to avoid blocking during import
        # The import chain (cmbagent -> autogen -> jsonschema) has blocking calls
        logger.info("Starting paper generation with Denario...")
        print("[Denario] 🚀 Starting paper generation workflow...", flush=True)
        
        # Send initial message immediately
        if writer:
            try:
                writer({
                    "denario_log": {
                        "message": "🚀 Starting paper generation workflow...",
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to send initial log: {e}")
        
        async def run_denario_paper_generation():
            """Run Denario paper generation in a thread to avoid blocking imports."""
            # Create a queue to pass log messages from thread to async context
            import queue
            log_queue = queue.Queue(maxsize=1000)
            
            def _generate_paper():
                try:
                    # Import Denario inside the thread to avoid blocking the event loop
                    from src.lib.denario.denario import Denario
                    from src.lib.denario.paper_agents.journal import Journal
                    from src.lib.denario.config import INPUT_FILES, IDEA_FILE, METHOD_FILE, RESULTS_FILE
                    
                    # Helper function to queue log messages (will be processed in async context)
                    def send_log(message: str):
                        """Queue log message to be sent to frontend."""
                        try:
                            log_queue.put(message, block=False)
                        except queue.Full:
                            pass  # Skip if queue is full
                    
                    def _generate_theoretical_results(den, outline, send_log_fn):
                        """Generate theoretical results without code execution."""
                        from langchain_openai import ChatOpenAI
                        from langchain_google_genai import ChatGoogleGenerativeAI
                        from langchain_anthropic import ChatAnthropic
                        from pathlib import Path as PathLib
                        
                        # Read idea and methods
                        idea_file = PathLib(project_dir) / INPUT_FILES / IDEA_FILE
                        method_file = PathLib(project_dir) / INPUT_FILES / METHOD_FILE
                        
                        idea_content = ""
                        method_content = ""
                        
                        if idea_file.exists():
                            with idea_file.open("r", encoding="utf-8") as f:
                                idea_content = f.read()
                        
                        if method_file.exists():
                            with method_file.open("r", encoding="utf-8") as f:
                                method_content = f.read()
                        
                        # Determine LLM based on available keys
                        llm = None
                        if den.keys.OPENAI:
                            llm = ChatOpenAI(
                                model="gpt-4o-mini",
                                temperature=0.7,
                                openai_api_key=den.keys.OPENAI
                            )
                        elif den.keys.GEMINI:
                            llm = ChatGoogleGenerativeAI(
                                model="gemini-2.0-flash-exp",
                                temperature=0.7,
                                google_api_key=den.keys.GEMINI
                            )
                        elif den.keys.ANTHROPIC:
                            llm = ChatAnthropic(
                                model="claude-3-5-sonnet-20241022",
                                temperature=0.7,
                                anthropic_api_key=den.keys.ANTHROPIC
                            )
                        else:
                            raise ValueError("No API keys available for theoretical results generation")
                        
                        # Get results section description from outline
                        results_section = next(
                            (s for s in outline.get('sections', []) 
                             if s.get('id') == 'results' or 'result' in s.get('title', '').lower()),
                            None
                        )
                        results_guidance = ""
                        if results_section:
                            results_guidance = f"\n\nFocus on: {results_section.get('description', '')}"
                            if results_section.get('subsections'):
                                results_guidance += "\n\nSubsections to cover:\n"
                                for sub in results_section['subsections']:
                                    if isinstance(sub, dict):
                                        results_guidance += f"- {sub.get('title', '')}: {sub.get('description', '')}\n"
                                    else:
                                        results_guidance += f"- {sub}\n"
                        
                        # Generate theoretical results
                        prompt = f"""Based on the research idea and methodology below, generate theoretical results and findings.

IMPORTANT: This is a theoretical research paper. Do NOT generate code, do NOT suggest running experiments, do NOT install packages.
Focus on:
- Theoretical analysis and findings
- Literature-based comparisons
- Expected outcomes based on existing research
- Theoretical performance metrics
- Conceptual insights and implications
{results_guidance}

Research Idea:
{idea_content}

Methodology:
{method_content}

Generate comprehensive theoretical results that would be expected from this research approach, based on existing literature and theoretical frameworks. Write in a clear, academic style suitable for a scientific paper results section."""
                        
                        send_log_fn("📊 Analyzing research and generating theoretical findings...")
                        response = llm.invoke(prompt)
                        results_text = response.content if hasattr(response, 'content') else str(response)
                        
                        # Write results to file
                        results_path = PathLib(project_dir) / INPUT_FILES / RESULTS_FILE
                        results_path.parent.mkdir(parents=True, exist_ok=True)
                        with results_path.open("w", encoding="utf-8") as f:
                            f.write(results_text)
                        
                        # Update den.research object
                        den.research.results = results_text
                        den.research.plot_paths = []  # No plots for theoretical results
                    
                    # Initialize Denario with project directory
                    den = Denario(project_dir=project_dir)
                    
                    # Set data description from outline before running research phase
                    # Combine all section descriptions into a single data description
                    combined_description = "Research topic based on outline:\n\n"
                    for section in outline.get('sections', []):
                        combined_description += f"## {section.get('title', 'Section')}\n"
                        combined_description += f"{section.get('description', '')}\n\n"
                        if section.get('subsections'):
                            for sub in section['subsections']:
                                if isinstance(sub, dict):
                                    combined_description += f"- {sub.get('title', '')}: {sub.get('description', '')}\n"
                    
                    # This creates the data_description.md file that the research workflow expects
                    den.set_data_description(data_description=combined_description)
                    logger.info("Data description set from outline")
                    print("[Denario] 📋 Data description created from outline", flush=True)
                    send_log("📋 Data description created from outline")
                    
                    # Always run the research phase before generating the paper
                    # The research files (idea.md, methods.md, results.md) don't exist yet,
                    # so we need to generate them through the research workflow
                    logger.info("Running research phase (idea, method, results)...")
                    print("[Denario] 🔬 Starting research phase...", flush=True)
                    send_log("🔬 Starting research phase...")
                    
                    # Step 1: Generate research idea based on data description
                    print("[Denario] 📝 Generating research idea...", flush=True)
                    send_log("📝 Generating research idea...")
                    # Use Denario's original default model configuration for stability
                    den.get_idea(mode="fast")
                    logger.info("Research idea generated")
                    send_log("✅ Research idea generated")
                    
                    # Step 2: Generate methodology to test the idea
                    print("[Denario] 🔬 Generating methodology...", flush=True)
                    send_log("🔬 Generating methodology...")
                    # Use Denario's original default model configuration for stability
                    den.get_method(mode="fast")
                    logger.info("Methodology generated")
                    send_log("✅ Methodology generated")
                    
                    # Step 3: Generate results (theoretical or experimental)
                    # Default: run experiments (to get plots) but keep them lightweight.
                    # Skip experiments if outline signals theoretical-only or env forces theoretical.
                    outline_text = json.dumps(outline, indent=2).lower()

                    # Theoretical-only indicators (these should ALWAYS skip experiments)
                    theoretical_indicators = [
                        "theoretical", "literature-based", "literature review", "conceptual",
                        "no code", "no implementation", "theoretical analysis", "theoretical study",
                        "literature analysis", "survey", "review paper", "literature survey"
                    ]

                    has_theoretical_indicator = any(indicator in outline_text for indicator in theoretical_indicators)

                    # Run experiments unless theoretical indicators are present
                    requires_experiments = not has_theoretical_indicator

                    import os
                    force_theoretical = os.getenv("DENARIO_FORCE_THEORETICAL", "false").lower() == "true"

                    lightweight_constraints = (
                        "Lightweight only: no package installation; no internet fetch; "
                        "prefer built-ins; small synthetic data; keep runtime under 3 minutes; "
                        "avoid heavy training/large downloads; CPU-friendly."
                    )

                    if requires_experiments and not force_theoretical:
                        print("[Denario] 🧪 Running experiments (lightweight: no installs, small synthetic data, <3min)...", flush=True)
                        send_log("🧪 Running experiments (lightweight: no installs, small synthetic data, <3min)...")
                        experiments_succeeded = False
                        last_error = None
                        for attempt in range(2):
                            try:
                                logger.info(f"Attempt {attempt+1}/2 for experimental results (async path)")
                                den.get_results(
                                    hardware_constraints=lightweight_constraints,
                                    max_n_attempts=3,
                                    max_n_steps=3,
                                )
                                experiments_succeeded = True
                                logger.info("Results generated via experiments (async path)")
                                send_log("✅ Results generated")
                                break
                            except Exception as exp_err:
                                last_error = exp_err
                                logger.warning(f"Experiment attempt {attempt+1} failed (async path): {exp_err}")
                                send_log(f"⚠️ Experiment attempt {attempt+1} failed; retrying...")
                        if not experiments_succeeded:
                            logger.warning(
                                f"All experimental attempts failed in async path (last error: {last_error}). "
                                "Falling back to theoretical results."
                            )
                            print("[Denario] ⚠️ Experiments failed; falling back to theoretical results.", flush=True)
                            send_log("⚠️ Experiments failed; falling back to theoretical results.")
                            _generate_theoretical_results(den, outline, send_log)
                            logger.info("Theoretical results generated after experiment failure (async path)")
                            send_log("✅ Theoretical results generated")
                    else:
                        if force_theoretical and requires_experiments:
                            logger.info("⚠️ Code execution requested but DENARIO_FORCE_THEORETICAL=true - using theoretical mode")
                            print("[Denario] ⚠️ Code execution disabled by DENARIO_FORCE_THEORETICAL - using theoretical mode", flush=True)
                        # Generate theoretical results only (no code execution)
                        print("[Denario] 📚 Generating theoretical results (no code execution)...", flush=True)
                        send_log("📚 Generating theoretical results based on research...")
                        _generate_theoretical_results(den, outline, send_log)
                        logger.info("Theoretical results generated")
                        send_log("✅ Theoretical results generated")
                    
                    print("[Denario] ✅ Research phase completed", flush=True)
                    send_log("✅ Research phase completed")
                    
                    # Step 4: Generate paper from research results
                    # The outline guides the structure, but content comes from actual research
                    print("[Denario] 📄 Generating paper from research results...", flush=True)
                    send_log("📄 Generating paper from research results...")
                    # Use Denario's internal default models for paper writing
                    den.get_paper(
                        journal=Journal.NONE,
                        writer="scientist",
                        cmbagent_keywords=False,
                        add_citations=True,
                        outline=outline,  # Pass outline directly to Denario (guides structure)
                    )
                    send_log("✅ Paper generation completed")
                except Exception as e:
                    # Log full traceback for debugging
                    import traceback
                    full_traceback = traceback.format_exc()
                    logger.error(f"Error inside Denario.get_paper: {e}\nFull traceback:\n{full_traceback}", exc_info=True)
                    print(f"[Denario] ❌ Error in paper generation:\n{full_traceback}", flush=True)
                    try:
                        log_queue.put(f"❌ Error: {str(e)}", block=False)
                    except queue.Full:
                        pass
                    raise RuntimeError(f"Denario paper generation failed: {str(e)}\n\nTraceback:\n{full_traceback}") from e
            
            # Process log queue in async context and run paper generation in thread
            generation_done = False
            
            async def process_logs():
                """Process log messages from queue and send to frontend."""
                while True:
                    try:
                        # Check queue with timeout
                        try:
                            log_message = log_queue.get(timeout=0.1)
                            if writer:
                                try:
                                    writer({
                                        "denario_log": {
                                            "message": log_message,
                                        }
                                    })
                                    logger.debug(f"Sent log to frontend: {log_message}")
                                except Exception as e:
                                    logger.warning(f"Failed to send log via writer: {e}")
                        except queue.Empty:
                            # If generation is done and queue is empty, exit
                            if generation_done:
                                # Process any remaining messages
                                await asyncio.sleep(0.3)
                                try:
                                    # Try one more time to get any final messages
                                    while True:
                                        log_message = log_queue.get_nowait()
                                        if writer:
                                            writer({
                                                "denario_log": {
                                                    "message": log_message,
                                                }
                                            })
                                except queue.Empty:
                                    break
                                break
                            else:
                                # Continue checking
                                await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.warning(f"Error processing log: {e}")
                        break
            
            # Start log processing task
            log_task = asyncio.create_task(process_logs())
            
            try:
                # Run in thread to avoid blocking filesystem operations during import
                await asyncio.to_thread(_generate_paper)
                # Mark generation as complete
                generation_done = True
            finally:
                # Wait for remaining logs to be processed
                await asyncio.sleep(1.0)
                if not log_task.done():
                    log_task.cancel()
                    try:
                        await log_task
                    except asyncio.CancelledError:
                        pass
        
        # Run Denario paper generation
        # This is a long-running operation, so we catch any exceptions and provide better error messages
        try:
            await run_denario_paper_generation()
            
            logger.info("Paper generation completed successfully")
            
            # Final success message with file links
            # Use async check for file existence to avoid blocking
            paper_path = Path(project_dir) / "paper"
            paper_exists = await asyncio.to_thread(paper_path.exists)
            
            if paper_exists:
                latex_file = paper_path / "paper_v4_final.tex"
                pdf_file = paper_path / "paper_v4_final.pdf"
                
                latex_exists = await asyncio.to_thread(latex_file.exists)
                pdf_exists = await asyncio.to_thread(pdf_file.exists)
                
                final_message = f"✅ Paper '{paper_name}' generated successfully!\n\n"
                final_message += f"📄 LaTeX file: {latex_file}\n"
                final_message += f"🔗 Download LaTeX: /api/paper/latex\n"
                
                if pdf_exists:
                    final_message += f"📕 PDF file: {pdf_file}\n"
                    final_message += f"🔗 View PDF: /api/paper/pdf\n"
                else:
                    final_message += f"⚠️ PDF not generated (xelatex may not be installed)\n"
                    final_message += f"🔗 Convert to PDF: /api/paper/convert-to-pdf\n"
            else:
                final_message = f"✅ Paper generation workflow completed. Check {paper_path} for generated files."
            
            # Emit final message if writer available
            if writer:
                try:
                    writer({
                        "denario_complete": {
                            "message": final_message,
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit completion via writer: {e}")
            
            print(f"[Denario] {final_message}", flush=True)
            return final_message
        except RuntimeError as e:
            # Re-raise RuntimeError from Denario execution with better context
            import traceback
            full_traceback = traceback.format_exc()
            error_msg = f"❌ Error during Denario paper generation: {str(e)}"
            logger.error(f"{error_msg}\nFull traceback:\n{full_traceback}", exc_info=True)
            if writer:
                try:
                    writer({
                        "denario_error": {
                            "message": error_msg,
                        }
                    })
                except Exception:
                    pass
            print(f"[Denario] {error_msg}", flush=True)
            print(f"[Denario] Full traceback:\n{full_traceback}", flush=True)
            raise  # Re-raise to be caught by outer exception handler
            
    except FileNotFoundError as e:
        # Check if it's about xelatex (LaTeX compiler not installed)
        error_str = str(e)
        if "xelatex" in error_str.lower():
            # LaTeX files were generated, but PDF compilation failed due to missing xelatex
            paper_path = Path(project_dir) / "paper"
            latex_files_exist = paper_path.exists() and any(paper_path.rglob("*.tex"))
            if latex_files_exist:
                error_msg = f"⚠️ LaTeX files generated successfully, but PDF compilation failed because 'xelatex' is not installed.\n\nTo install xelatex:\n  sudo apt-get install texlive-xetex texlive-latex-extra\n\nLaTeX source files are available at: {paper_path}"
            else:
                error_msg = f"❌ PDF compilation failed: xelatex not found. Install with: sudo apt-get install texlive-xetex"
            logger.warning(error_msg)
            return error_msg
        elif "plan_outline.json" in error_str or "outline" in error_str.lower():
            error_msg = f"❌ Outline file not found. Please create an outline first using the outline-agent. Expected location: {project_dir}/plan_outline.json"
        else:
            error_msg = f"❌ File not found: {error_str}"
        logger.error(f"{error_msg} (Original error: {e})", exc_info=True)
        return error_msg
    except (ValueError, json.JSONDecodeError) as e:
        error_msg = f"❌ Invalid outline format: {e}"
        logger.error(error_msg, exc_info=True)
        return error_msg
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        error_msg = f"❌ Error generating paper: {str(e)}"
        logger.error(f"{error_msg}\nFull traceback:\n{full_traceback}", exc_info=True)
        if writer:
            try:
                writer({
                    "denario_error": {
                        "message": error_msg,
                    }
                })
            except Exception:
                pass
        print(f"[Denario] {error_msg}", flush=True)
        print(f"[Denario] Full traceback:\n{full_traceback}", flush=True)
        # Include traceback in return message for debugging
        return f"{error_msg}\n\nTraceback:\n{full_traceback}"


# Create configurable wrapper that extracts thread_id from config
from langchain_core.runnables import RunnableConfig

# Context variable to store config (set by tools_node)
import contextvars
_config_var = contextvars.ContextVar('langgraph_config', default=None)

def _sync_wrapper(project_dir: str | None = None, paper_name: str = "generated_paper", **kwargs):
    """Wrapper to extract config from execution context or contextvars."""
    # Try to get config from contextvars first (set by tools_node)
    config = _config_var.get()
    
    # If not in contextvars, try get_config()
    if not config:
        try:
            from langchain_core.runnables import get_config
            config = get_config()
            logger.debug(f"Wrapper: Got config from get_config(): {type(config)}")
        except Exception as e:
            logger.debug(f"Wrapper: Could not get config from get_config(): {e}")
    
    return sync_generate_paper_from_outline(project_dir=project_dir, paper_name=paper_name, config=config)

async def _async_wrapper(project_dir: str | None = None, paper_name: str = "generated_paper", **kwargs):
    """Async wrapper to extract config from execution context or contextvars."""
    # Try to get config from contextvars first (set by tools_node)
    config = _config_var.get()
    
    # If not in contextvars, try get_config()
    if not config:
        try:
            from langchain_core.runnables import get_config
            config = get_config()
            logger.debug(f"Wrapper: Got config from get_config(): {type(config)}")
        except Exception as e:
            logger.debug(f"Wrapper: Could not get config from get_config(): {e}")
    
    return await async_generate_paper_from_outline(project_dir=project_dir, paper_name=paper_name, config=config)

# Create the tool
generate_paper_from_outline = StructuredTool.from_function(
    name="generate_paper_from_outline",
    description="Generates a scientific paper from a research outline. The outline must be available at project/plan_outline.json (or project/threads/{thread_id}/plan_outline.json for thread-specific storage). The tool will read this outline and use the Denario workflow to generate the paper. The generated paper (LaTeX files) will be saved to the specified project directory. If thread_id is available in the config, files will be stored in a thread-specific directory.",
    func=_sync_wrapper,
    coroutine=_async_wrapper,
)
