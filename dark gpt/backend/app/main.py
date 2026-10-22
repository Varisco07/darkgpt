"""Composition root dell'applicazione DarkGPT.

Questo modulo contiene solo composizione: applicazione FastAPI, middleware,
gestione errori e montaggio dei router. La logica di business vive in
`app/services` e `app/tools`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routers import chat, findings, projects, reports, scope, settings, tools
from .core.config import get_settings
from .core.db import init_db
from .core.errors import AppError
from .core.logging import get_logger, setup_logging
from .tools import register_builtin_tools

logger = get_logger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ciclo di vita dell'applicazione: DB e registry dei tool."""
    setup_logging(logging.INFO)
    init_db()
    register_builtin_tools()
    logger.info("startup_complete", extra={"extra_fields": {"app": get_settings().app_name}})
    yield
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    """Crea e configura l'applicazione FastAPI."""
    app_settings = get_settings()
    application = FastAPI(
        title=f"{app_settings.app_name} API",
        version=app_settings.app_version,
        description=(
            "Piattaforma di sicurezza applicativa: scope manager, analisi "
            "statica, gestione dei finding, report e ricerca assistita da LLM."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):  # noqa: ANN001, ANN202
        """Applica gli header di sicurezza di base a ogni risposta."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

    # -- gestione errori -------------------------------------------------
    @application.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "la richiesta non rispetta lo schema atteso",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    # -- router ----------------------------------------------------------
    # Tutte le API applicative sono sotto il prefisso /api; /health resta
    # alla radice per l'ispezione da parte dei monitor di servizio.
    application.include_router(projects.router, prefix="/api")
    application.include_router(scope.router, prefix="/api")
    application.include_router(findings.router, prefix="/api")
    application.include_router(tools.router, prefix="/api")
    application.include_router(chat.router, prefix="/api")
    application.include_router(reports.router, prefix="/api")
    application.include_router(settings.router, prefix="/api")

    @application.get("/health", tags=["system"], summary="Stato di salute")
    def health() -> dict:
        """Verifica che il servizio e il database siano operativi."""
        from sqlalchemy import text

        from .core.db import session_scope
        from .tools.registry import registry

        database_status = "ok"
        try:
            with session_scope() as session:
                session.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 - la salute del DB non deve far fallire la risposta
            database_status = "error"

        described = registry.describe()
        provider = settings_provider_name()
        return {
            "status": "ok" if database_status == "ok" else "degraded",
            "version": app_settings.app_version,
            "database": database_status,
            "llm_provider": provider,
            "llm_configured": app_settings.llm_configured,
            "tools_available": sum(
                1 for item in described if item["availability"] == "available"
            ),
            "tools_total": len(described),
        }

    return application


def settings_provider_name() -> str:
    """Nome del provider LLM attivo."""
    from .ai.provider import get_provider

    return get_provider().name


app = create_app()
