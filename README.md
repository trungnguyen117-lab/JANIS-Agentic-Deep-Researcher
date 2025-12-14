# JANIS Agentic Deep Researcher

Research automation system with dynamic paper outline support, integrating Denario paper generation with orchestrator planning.

## Quick Start

```bash
# 1. Install dependencies
make install              # Both backend and frontend
# Or separately:
make install-backend-dev  # Backend with dev dependencies
make install-frontend     # Frontend

# 2. Configure (unified .env for both frontend and backend)
cp .env.example .env
# Edit .env and add your API keys and frontend config

# 3. Start development servers
make dev                  # Both backend and frontend
# Or separately:
make dev-backend          # Backend (LangGraph Studio)
make dev-frontend         # Frontend (Next.js)
```

## Prerequisites

- Python 3.12+ and [uv](https://github.com/astral-sh/uv)
- Node.js 18+
- **LaTeX Compiler (for PDF generation)**: `xelatex` and `bibtex`
  ```bash
  # Ubuntu/Debian
  sudo apt-get update
  sudo apt-get install texlive-xetex texlive-latex-extra
  
  # macOS (with Homebrew)
  brew install --cask mactex
  
  # Or minimal install
  brew install basictex
  ```
  
  **Note**: LaTeX files are generated even without the compiler, but PDF compilation will fail. You can use the `.tex` files directly or compile them manually later.

## Project Structure

```
├── backend/              # Python backend (LangGraph, Denario)
│   └── src/lib/
│       ├── denario/      # Paper generation
│       └── deepagents/   # Deep Agents framework
├── .env                  # Unified config (create from .env.example)
├── frontend/             # Next.js frontend
├── plan/                 # Implementation docs
│   ├── CONTEXT.md       # Architecture overview
│   └── PLAN.md          # Implementation plan
└── Makefile             # Development commands
```

## Common Commands

```bash
make help                # Show all commands
make install             # Install both backend and frontend
make install-backend-dev # Install backend with dev deps
make install-frontend    # Install frontend deps
make test                # Run all tests
make lint                # Lint code
make format              # Format code
make dev                 # Start both servers
```

## Documentation

- **Quick Start**: See `QUICKSTART.md` for detailed setup
- **Architecture**: `plan/CONTEXT.md` - System architecture
- **Implementation**: `plan/PLAN.md` - Development plan
- **OpenAI Setup**: `backend/docs/OPENAI_COMPATIBLE_SETUP.md` - Custom API endpoints

## Features

- Dynamic paper outline system
- Denario paper generation integration
- LaTeX paper generation (requires xelatex for PDF compilation)
- OpenAI-compatible API support
- Backward compatible

## Paper Generation

The system uses Denario to generate scientific papers from outlines. The paper generation process:

1. **Creates an outline** using the outline agent
2. **Generates LaTeX source files** for each section
3. **Compiles to PDF** (requires xelatex installed)

**Output locations:**
- LaTeX files: `project/paper/temp/*.tex`
- Compiled PDF: `project/paper/temp/*.pdf` (if xelatex is installed)

If xelatex is not installed, LaTeX files are still generated and can be compiled manually or used as-is.

## License

MIT
