"""Application state and dependencies."""

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from vakit_pi.domain.models import PrayerSettings
from vakit_pi.infrastructure.audio import BaseAudioPlayer, get_best_player
from vakit_pi.infrastructure.bluetooth import BluetoothctlAdapter
from vakit_pi.infrastructure.event_bus import InMemoryEventBus
from vakit_pi.infrastructure.scheduler import APSchedulerAdapter
from vakit_pi.infrastructure.settings_repository import JsonSettingsRepository
from vakit_pi.infrastructure.system_volume import PulseAudioVolumeAdapter
from vakit_pi.services.adhan_service import AdhanService
from vakit_pi.services.bluetooth_manager import BluetoothManager
from vakit_pi.services.prayer_service import PrayerService
from vakit_pi.services.scheduler_service import SchedulerService


@dataclass
class AppState:
    """Application state container."""

    settings: PrayerSettings
    settings_repository: JsonSettingsRepository
    prayer_service: PrayerService
    adhan_service: AdhanService
    scheduler_service: SchedulerService
    scheduler_adapter: APSchedulerAdapter
    event_bus: InMemoryEventBus
    audio_player: BaseAudioPlayer
    bluetooth_adapter: BluetoothctlAdapter
    bluetooth_manager: BluetoothManager
    system_volume: PulseAudioVolumeAdapter
    started_at: datetime
    audio_dir: Path


# Global application state (singleton)
_app_state: AppState | None = None


def _current_settings() -> PrayerSettings:
    """Güncel ayarlar (route'lar state.settings'i yeni nesneyle değiştirebilir)."""
    return get_app_state().settings


async def _update_settings_fields(**changes: Any) -> None:
    """Ayarların bazı alanlarını değiştir, servislere bildir ve diske kaydet."""
    state = get_app_state()
    new_settings = replace(state.settings, **changes)
    state.settings = new_settings
    state.adhan_service.update_settings(new_settings)
    await state.settings_repository.save(new_settings)


async def initialize_app_state(
    settings_path: Path | None = None,
    audio_dir: Path | None = None,
) -> AppState:
    """
    Initialize application state.

    Args:
        settings_path: Ayar dosyası yolu
        audio_dir: Ezan ses dosyaları dizini

    Returns:
        Initialized AppState
    """
    global _app_state

    if _app_state is not None:
        return _app_state

    # Repository ve ayarlar
    settings_repo = JsonSettingsRepository(settings_path)
    settings = await settings_repo.load()

    # Audio directory
    if audio_dir is None:
        audio_dir = Path(__file__).parent.parent / "assets" / "audio"

    # Infrastructure
    event_bus = InMemoryEventBus()
    audio_player = get_best_player()
    scheduler_adapter = APSchedulerAdapter()
    bluetooth_adapter = BluetoothctlAdapter()
    system_volume = PulseAudioVolumeAdapter()

    # Services
    bluetooth_manager = BluetoothManager(
        bluetooth=bluetooth_adapter,
        audio=system_volume,
        get_settings=_current_settings,
        update_settings=_update_settings_fields,
    )

    prayer_service = PrayerService(
        location=settings.location,
        fajr_isha_method=settings.fajr_isha_method,
        asr_fiqh=settings.asr_fiqh,
        offsets=settings.offsets,
    )

    adhan_service = AdhanService(
        audio_player=audio_player,
        settings=settings,
        event_bus=event_bus,
        audio_dir=audio_dir,
        output_ready=bluetooth_manager.output_ready,
    )

    scheduler_service = SchedulerService(
        prayer_service=prayer_service,
        adhan_service=adhan_service,
        scheduler=scheduler_adapter,
        event_bus=event_bus,
    )

    _app_state = AppState(
        settings=settings,
        settings_repository=settings_repo,
        prayer_service=prayer_service,
        adhan_service=adhan_service,
        scheduler_service=scheduler_service,
        scheduler_adapter=scheduler_adapter,
        event_bus=event_bus,
        audio_player=audio_player,
        bluetooth_adapter=bluetooth_adapter,
        bluetooth_manager=bluetooth_manager,
        system_volume=system_volume,
        started_at=datetime.now(),
        audio_dir=audio_dir,
    )

    return _app_state


def get_app_state() -> AppState:
    """Get current application state."""
    if _app_state is None:
        raise RuntimeError("Application state not initialized")
    return _app_state


async def shutdown_app_state() -> None:
    """Shutdown application state."""
    global _app_state

    if _app_state is not None:
        await _app_state.scheduler_service.stop()
        _app_state.scheduler_adapter.shutdown()
        _app_state = None
