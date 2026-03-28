"""FastAPI app factory: mount routers, CORS, lifespan. Business logic lives in api/* and services/*."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: log LLM/persistence mode; shutdown: cancel background tasks."""
    import sys

    if sys.version_info < (3, 10):
        logger.critical("Python 3.10+ is required (langgraph, mcp). Current: %s", sys.version)
        raise SystemExit(1)
    try:
        import langgraph  # noqa: F401
        import mcp  # noqa: F401
    except ImportError as e:
        logger.critical("Required packages missing: langgraph, mcp. pip install -r apps/backend/requirements.txt — %s", e)
        raise SystemExit(1) from e
    logger.info("Required stack OK: LangGraph + MCP packages importable")

    logger.info("LLM provider order: %s", settings.llm_provider_order)
    if settings.ollama_base_url and settings.ollama_model:
        logger.info("Ollama configured: %s (model=%s)", settings.ollama_base_url, settings.ollama_model)
    if settings.model_file_path:
        logger.info("Local model configured: %s", settings.model_path)
    else:
        logger.info("Local model not configured (MODEL_PATH unset or file missing)")
    if settings.remote_llm_api_key:
        logger.info("Remote LLM API key configured (REMOTE_LLM_API_KEY set)")
    else:
        logger.info("Remote LLM API not configured (REMOTE_LLM_API_KEY unset); will use local or mock when needed")
    if not settings.ollama_base_url and not settings.model_file_path and not settings.remote_llm_api_key:
        logger.info("No ollama/remote/local model configured; using mock LLM. Set OLLAMA_BASE_URL or MODEL_PATH for real output")
    from apps.backend.db.google_client import spreadsheet_available

    if not settings.credentials_path:
        logger.warning("GOOGLE_CREDS_PATH not set or file not found; persistence will use in-memory fake")
    elif spreadsheet_available():
        if settings.spreadsheet_id:
            logger.info("Google persistence configured (GOOGLE_CREDS_PATH + SPREADSHEET_ID)")
        else:
            logger.info(
                "Google persistence configured (GOOGLE_CREDS_PATH + GOOGLE_SHEETS_SPREADSHEET_NAME=%s; find or create)",
                settings.google_sheets_spreadsheet_name or "all-doing-bot cohorts",
            )
    else:
        logger.warning(
            "Set GOOGLE_CREDS_PATH and either SPREADSHEET_ID or GOOGLE_SHEETS_SPREADSHEET_NAME for real persistence"
        )
    yield
    await asyncio.sleep(0.5)


def create_app() -> FastAPI:
    """Build FastAPI app with CORS and all HTTP routers."""
    from apps.backend.api.routes_admin import router as admin_router
    from apps.backend.api.routes_chat import router as chat_router
    from apps.backend.api.routes_health import router as health_router
    from apps.backend.api.routes_pipeline import router as pipeline_router
    from apps.backend.api.routes_workflows import router as workflows_router

    app = FastAPI(
        title="all-doing-bot",
        description="LLM-powered query -> cohort/action pipeline, results in Google Sheets",
        lifespan=lifespan,
    )

    _cors_origins = settings.cors_origins_list
    if not _cors_origins:
        _cors_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
        logger.warning("CORS_ALLOW_ORIGINS not set, using localhost defaults")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(admin_router)
    app.include_router(pipeline_router)
    app.include_router(workflows_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
