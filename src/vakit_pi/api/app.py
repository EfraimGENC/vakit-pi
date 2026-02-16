"""FastAPI application factory."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from vakit_pi import __version__
from vakit_pi.api.dependencies import initialize_app_state, shutdown_app_state
from vakit_pi.api.routes import router as api_router

if TYPE_CHECKING:
    from vakit_pi.api.dependencies import AppState

logger = logging.getLogger(__name__)

# Background task referansları
_midnight_task: asyncio.Task[None] | None = None
_bt_connect_task: asyncio.Task[None] | None = None


async def _midnight_scheduler_loop(state: "AppState") -> None:
    """Her gece yarısı ertesi günün namaz vakitlerini planlar."""
    while True:
        try:
            now = datetime.now(state.prayer_service.timezone)
            tomorrow_date = now.date() + timedelta(days=1)
            next_midnight = datetime.combine(
                tomorrow_date,
                datetime.min.time(),
                tzinfo=state.prayer_service.timezone,
            )

            # Gece yarısına kadar bekle (+1 dakika güvenlik marjı)
            wait_seconds = (next_midnight - now).total_seconds() + 60
            logger.info(f"Gece yarısı planlaması için {wait_seconds / 3600:.1f} saat bekleniyor.")

            await asyncio.sleep(wait_seconds)

            # Yeni günün vakitlerini planla
            logger.info("Gece yarısı: Yeni gün için namaz vakitleri planlanıyor...")
            scheduled = state.scheduler_service.schedule_day()
            logger.info(f"Gece yarısı planlaması tamamlandı: {scheduled} iş planlandı.")

        except asyncio.CancelledError:
            logger.info("Gece yarısı planlama döngüsü iptal edildi.")
            break
        except Exception as e:
            logger.error(f"Gece yarısı planlama hatası: {e}", exc_info=True)
            # Hata durumunda 1 saat bekle ve tekrar dene
            await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    global _midnight_task, _bt_connect_task

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
    scheduled_today = state.scheduler_service.schedule_day()

    # Bugün için planlanan iş yoksa (tüm vakitler geçmişse) yarını planla
    if scheduled_today == 0:
        tomorrow = datetime.now(state.prayer_service.timezone) + timedelta(days=1)
        logger.info("Bugün için planlanan vakit yok, yarın planlanıyor.")
        state.scheduler_service.schedule_day(tomorrow)

    # Gece yarısı planlama döngüsünü background task olarak başlat
    _midnight_task = asyncio.create_task(_midnight_scheduler_loop(state))
    logger.info("Gece yarısı planlama döngüsü başlatıldı.")

    # Bluetooth auto-connect
    bt_mac = state.settings.bluetooth_device_mac
    if bt_mac:
        _bt_connect_task = asyncio.create_task(state.bluetooth_adapter.auto_connect_loop(bt_mac))
        logger.info(f"Bluetooth auto-connect başlatıldı: {bt_mac}")

    logger.info("Vakit-Pi hazır!")

    yield

    # Shutdown
    logger.info("Vakit-Pi kapatılıyor...")

    # Background task'ları iptal et
    for task in [_midnight_task, _bt_connect_task]:
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

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
