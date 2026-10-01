"""FastAPI composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.bootstrap import bootstrap_admin
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.post_commit import set_job_dispatcher
from app.db.redis import close_redis, init_redis
from app.db.session import dispose_engine, get_session_factory
from app.middleware.db_session import DatabaseSessionMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.workers.queue import close_queue, enqueue_jobs, init_queue


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_redis()
    await init_queue()
    set_job_dispatcher(enqueue_jobs)
    factory = get_session_factory()
    async with factory() as session:
        await bootstrap_admin(session)
        await session.commit()
    yield
    await close_queue()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    configure_logging(settings.log_level, settings.log_json)
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.app_debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    application.add_middleware(DatabaseSessionMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return application


app = create_app()
