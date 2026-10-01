# Employee Management System

Modular monolith for employees, departments, attendance, leave, and reports.

## Run locally

1. Copy `.env.example` to `.env`.
2. Set `SECRET_KEY` to a random string of at least 32 characters.
3. Optionally set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` (at least 8 characters, with a letter and a number) to create the first admin on startup.
4. Start the stack:

```bash
docker compose up --build
```

The API runs migrations, then serves OpenAPI at `http://localhost:8000/docs`. The web app is at `http://localhost:3000`. Readiness is `GET /api/v1/health/ready`.

For UI development without rebuilding the image:

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8000`.

## Local checks

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/pytest
```

Integration tests start PostgreSQL and Redis with Docker. Unit tests do not.

Architecture and role rules are in [ARCHITECTURE.md](ARCHITECTURE.md).
