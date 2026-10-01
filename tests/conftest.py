"""Pytest environment. These values exist before the application is imported."""

import os

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ems:ems@localhost:5432/ems")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "")
