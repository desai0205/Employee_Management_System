.PHONY: install lint format typecheck test migrate up down

install:
	pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy app

test:
	pytest

migrate:
	alembic upgrade head

up:
	docker compose up --build

down:
	docker compose down
