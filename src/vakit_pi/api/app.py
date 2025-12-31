"""FastAPI application factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from vakit_pi import __version__
from vakit_pi.api.dependencies import initialize_app_state, shutdown_app_state
from vakit_pi.api.routes import router as api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info("Vakit-Pi başlatılıyor...")

    settings_path = getattr(app.state, "settings_path", None)
    audio_dir = getattr(app.state, "audio_dir", None)

    state = await initialize_app_state(
        settings_path=settings_path,
        audio_dir=audio_dir,
    )

    # Scheduler'ı başlat
    state.scheduler_adapter.start()
    state.scheduler_service.schedule_day()

    logger.info("Vakit-Pi hazır!")

    yield

    # Shutdown
    logger.info("Vakit-Pi kapatılıyor...")
    await shutdown_app_state()
    logger.info("Vakit-Pi kapatıldı.")


def create_app(
    settings_path: Path | None = None,
    audio_dir: Path | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """
    Create FastAPI application.

    Args:
        settings_path: Ayar dosyası yolu
        audio_dir: Ezan ses dosyaları dizini
        static_dir: Static dosyalar dizini (frontend)

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Vakit-Pi",
        description="Raspberry Pi için Namaz Vakti ve Ezan Uygulaması",
        version=__version__,
        lifespan=lifespan,
    )

    # Store config in app state
    app.state.settings_path = settings_path
    app.state.audio_dir = audio_dir

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Production'da kısıtlanmalı
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router, prefix="/api")

    # Static files (frontend)
    if static_dir is None:
        static_dir = Path(__file__).parent.parent / "web" / "static"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def serve_index() -> FileResponse:
            """Serve the main index.html."""
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return FileResponse(static_dir.parent / "index.html")

    # Health check
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy", "version": __version__}

    return app
