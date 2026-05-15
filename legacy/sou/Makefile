.PHONY: dev backend frontend migrate seed test lint format build

dev:
	$(MAKE) -j2 backend frontend

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python scripts/seed.py

test:
	cd backend && pytest
	cd frontend && npm run build

lint:
	cd backend && ruff check app scripts tests
	cd frontend && npm run lint

format:
	cd backend && ruff format app scripts tests
	cd frontend && npm run format

build:
	docker compose build
