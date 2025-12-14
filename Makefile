.PHONY: help install install-backend install-backend-dev install-frontend test test-backend test-frontend lint lint-backend lint-frontend format format-backend format-frontend type-check clean setup setup-backend setup-frontend dev dev-backend dev-frontend kill kill-backend kill-frontend

help:
	@echo "Available commands (using uv for backend, npm for frontend):"
	@echo ""
	@echo "Setup:"
	@echo "  make setup           - Show setup instructions for both backend and frontend"
	@echo "  make setup-backend  - Set up backend development environment"
	@echo "  make setup-frontend - Set up frontend development environment"
	@echo ""
	@echo "Installation:"
	@echo "  make install         - Install both backend and frontend dependencies"
	@echo "  make install-backend - Install backend package (uv sync)"
	@echo "  make install-backend-dev - Install backend with dev dependencies (uv sync --extra dev)"
	@echo "  make install-frontend - Install frontend dependencies (npm install)"
	@echo ""
	@echo "Testing:"
	@echo "  make test            - Run all tests (backend + frontend)"
	@echo "  make test-backend   - Run backend tests (uv run pytest)"
	@echo "  make test-frontend  - Run frontend tests (npm test)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint            - Lint both backend and frontend"
	@echo "  make lint-backend   - Lint backend (uv run ruff)"
	@echo "  make lint-frontend  - Lint frontend (npm run lint)"
	@echo "  make format         - Format both backend and frontend"
	@echo "  make format-backend - Format backend (uv run ruff format)"
	@echo "  make format-frontend - Format frontend (npm run format)"
	@echo "  make type-check     - Type check backend (uv run mypy)"
	@echo ""
	@echo "Development:"
	@echo "  make dev             - Start both backend and frontend dev servers"
	@echo "  make dev-backend    - Start backend dev server"
	@echo "  make dev-frontend   - Start frontend dev server (npm run dev)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           - Clean build artifacts and .venv"
	@echo "  make kill            - Kill all lingering dev processes (backend + frontend)"
	@echo "  make kill-backend    - Kill lingering backend processes"
	@echo "  make kill-frontend   - Kill lingering frontend processes"

setup:
	@echo "Setting up development environment..."
	@echo ""
	@echo "Backend:"
	@echo "  1. Install uv: https://github.com/astral-sh/uv"
	@echo "  2. Run: make setup-backend"
	@echo ""
	@echo "Frontend:"
	@echo "  1. Install Node.js (v18+ recommended)"
	@echo "  2. Run: make setup-frontend"

setup-backend:
	@echo "Setting up backend development environment with uv..."
	@echo "Installing uv: https://github.com/astral-sh/uv"
	@echo "Then run: make install-backend-dev"

setup-frontend:
	@echo "Setting up frontend development environment..."
	@echo "Make sure Node.js is installed, then run: make install-frontend"

install: install-backend install-frontend

install-backend:
	cd backend && uv sync
	@echo "Backend virtual environment created in backend/.venv"
	@echo "Activate with: source backend/.venv/bin/activate"
	@echo "Or use 'uv run' to run commands in the virtual environment"

install-backend-dev:
	cd backend && uv sync --extra dev
	@echo "Backend virtual environment created in backend/.venv"
	@echo "Activate with: source backend/.venv/bin/activate"
	@echo "Or use 'uv run' to run commands in the virtual environment"

install-frontend:
	cd frontend && npm install

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-cov:
	cd backend && uv run pytest --cov=src --cov-report=html --cov-report=term

test-frontend:
	cd frontend && npm test || echo "Frontend tests not configured"

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check src/

lint-frontend:
	cd frontend && npm run lint

format: format-backend format-frontend

format-backend:
	cd backend && uv run ruff format src/

format-frontend:
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,scss}" || echo "Prettier not configured, skipping"

type-check:
	cd backend && uv run mypy src/ --ignore-missing-imports

dev: dev-backend dev-frontend

dev-backend:
	@echo "Starting backend with LangGraph Studio..."
	@echo "Backend will be available at http://127.0.0.1:2024"
	@echo "Press Ctrl+C to stop"
	@rm -f /tmp/backend_stopping.lock; \
	cleanup_backend() { \
		if [ ! -f /tmp/backend_stopping.lock ]; then \
			touch /tmp/backend_stopping.lock; \
			echo ""; \
			echo "Stopping backend..."; \
			pkill -f "langgraph dev" 2>/dev/null || true; \
			pkill -f "uv run langgraph" 2>/dev/null || true; \
			lsof -ti:2024 | xargs kill -9 2>/dev/null || true; \
			rm -f /tmp/backend_stopping.lock; \
		fi; \
	}; \
	trap 'cleanup_backend; exit' INT TERM; \
	cd backend && uv sync && BG_JOB_ISOLATED_LOOPS=true uv run langgraph dev --port 2024 || cleanup_backend; \
	rm -f /tmp/backend_stopping.lock

dev-frontend:
	@echo "Starting frontend dev server..."
	@echo "Frontend will be available at http://localhost:3000"
	@echo "Press Ctrl+C to stop"
	@rm -f /tmp/frontend_stopping.lock; \
	cleanup_frontend() { \
		if [ ! -f /tmp/frontend_stopping.lock ]; then \
			touch /tmp/frontend_stopping.lock; \
			echo ""; \
			echo "Stopping frontend..."; \
			pkill -f "next dev" 2>/dev/null || true; \
			pkill -f "node.*next" 2>/dev/null || true; \
			lsof -ti:3000 | xargs kill -9 2>/dev/null || true; \
			rm -f /tmp/frontend_stopping.lock; \
		fi; \
	}; \
	trap 'cleanup_frontend; exit' INT TERM; \
	cd frontend && npm run dev || cleanup_frontend; \
	rm -f /tmp/frontend_stopping.lock

clean:
	rm -rf backend/build/
	rm -rf backend/dist/
	rm -rf backend/*.egg-info
	rm -rf backend/.pytest_cache/
	rm -rf backend/.mypy_cache/
	rm -rf backend/.ruff_cache/
	rm -rf backend/htmlcov/
	rm -rf backend/.venv/  # Remove uv virtual environment
	rm -rf frontend/node_modules/
	rm -rf frontend/.next/
	rm -rf frontend/out/
	rm -rf frontend/build/
	
	find backend -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find backend -type f -name "*.pyc" -delete 2>/dev/null || true

kill: kill-backend kill-frontend
	@echo "All dev processes killed"

kill-backend:
	@echo "Killing lingering backend processes..."
	@pkill -f "langgraph dev" 2>/dev/null || true
	@pkill -f "uv run langgraph" 2>/dev/null || true
	@lsof -ti:2024 | xargs kill -9 2>/dev/null || true
	@sleep 0.5
	@echo "Backend processes killed"

kill-frontend:
	@echo "Killing lingering frontend processes..."
	@pkill -f "next dev" 2>/dev/null || true
	@pkill -f "npm run dev" 2>/dev/null || true
	@pkill -f "node.*next" 2>/dev/null || true
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@sleep 0.5
	@echo "Frontend processes killed"
