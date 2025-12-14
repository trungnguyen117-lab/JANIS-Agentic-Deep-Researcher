# Quick Start Guide

## Setup (5 minutes)

### 1. Configuration

```bash
# From project root
cp .env.example .env
```

Edit `.env` and add your configuration:
```bash
# Required: At least one LLM API key
OPENAI_API_KEY=your_key_here
# or
ANTHROPIC_API_KEY=your_key_here
# or
GOOGLE_API_KEY=your_key_here

# Required: Frontend configuration
NEXT_PUBLIC_DEPLOYMENT_URL=http://127.0.0.1:2024
NEXT_PUBLIC_AGENT_ID=research-agent

# Optional: OpenAI-compatible endpoints (OpenRouter, Together AI, etc.)
OPENAI_BASE_URL=https://api.openrouter.ai/v1
```

### 2. Backend Setup

```bash
# From project root
make install-backend-dev
```

### 3. Frontend Setup

```bash
make install-frontend
```

### 4. Start Servers

```bash
# Start both
make dev

# Or separately:
make dev-backend    # Backend: http://localhost:8123
make dev-frontend   # Frontend: http://localhost:3000
```

## File Structure

- **Use root `Makefile`** for all commands
- **Unified config**: `.env` in project root (create from `.env.example`)
- Both backend and frontend read from root `.env`

## Troubleshooting

**Backend won't start?**
- Check `.env` exists in project root and has API keys
- Run `make install-backend-dev`

**Frontend won't start?**
- Check Node.js version: `node --version` (needs 18+)
- Run `cd frontend && npm install`

**Port conflicts?**
- Backend: 2024 (LangGraph API - configured in Makefile)
- Frontend: 3000 (Next.js)
- Kill lingering processes: `make kill` or `make kill-backend` / `make kill-frontend`

**CORS errors?**
- CORS is configured in `backend/langgraph.json` to allow requests from `http://localhost:3000` and `http://127.0.0.1:3000`
- Make sure backend is running on port 2024 (matches NEXT_PUBLIC_DEPLOYMENT_URL in .env)
- Restart backend after changing `langgraph.json` or `.env`

**Processes won't stop?**
- Run `make kill` to kill all lingering dev processes
- Or `make kill-backend` / `make kill-frontend` for specific services
