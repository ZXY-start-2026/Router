from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import create_engine_and_session_factory
from app.providers.model import ModelProvider
from app.providers.registry import ProviderRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app(
    settings_override: Settings | None = None,
    model_provider_override: ModelProvider | None = None,
) -> FastAPI:
    settings = settings_override or Settings.load()
    engine, session_factory = create_engine_and_session_factory(settings.database_url)
    providers = ProviderRegistry(settings, model_override=model_provider_override)

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.providers = providers
    app.state.model_provider = providers.model
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                }
            },
        )

    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
