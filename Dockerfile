FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    NODE_ENV=production

WORKDIR /app

# System deps: Python, Node, build tooling, LaTeX engine for PDF
# Note: On Ubuntu 24.04, python3-distutils is part of the default Python; no separate package.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    nodejs npm \
    curl ca-certificates git \
    texlive-xetex texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager) globally
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

# Copy project
COPY . /app

# -------- Backend setup --------
WORKDIR /app/backend

# Create virtualenv and install Python deps with uv
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install .

# -------- Frontend setup --------
WORKDIR /app/frontend

RUN npm ci && npm run build

# -------- Runtime configuration --------
WORKDIR /app/backend

# Volumes for persistent data:
# - /app/project: generated outlines, threads, papers, etc.
# - /app/frontend/node_modules: cached dependencies
# - /app/frontend/.next: Next.js build cache/output
VOLUME ["/app/project", "/app/frontend/node_modules", "/app/frontend/.next"]

# Expose backend (LangGraph HTTP API) and frontend ports
EXPOSE 8000 3000

# Simple process supervisor to run both backend and frontend
# - Backend: langgraph dev --no-reload (serves HTTP API)
# - Frontend: next start (serves UI)
CMD /bin/bash -lc '\
  source .venv/bin/activate && \
  # Start backend LangGraph server (no reload) \
  langgraph dev --no-reload --host 0.0.0.0 --port 8000 & \
  # Start frontend Next.js server \
  cd /app/frontend && \
  npm run start -- --port 3000 --hostname 0.0.0.0 \
'


