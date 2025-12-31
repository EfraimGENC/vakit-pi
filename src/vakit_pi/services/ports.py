"""Service layer interfaces (ports)."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date, datetime

from vakit_pi.domain.events import DomainEvent
from vakit_pi.domain.models import (
    Location,
    PrayerSettings,
    PrayerTimes,
)


class PrayerTimeCalculatorPort(ABC):
    """Namaz vakti hesaplama arayüzü (port)."""

    @abstractmethod
    def calculate(self, target_date: date) -> PrayerTimes:
        """Belirtilen tarih için namaz vakitlerini hesapla."""

    @abstractmethod
    def calculate_range(self, start_date: date, days: int) -> list[PrayerTimes]:
        """Belirtilen tarihten itibaren n gün için vakitleri hesapla."""


class AudioPlayerPort(ABC):
    """Ses çalma arayüzü (port)."""

    @abstractmethod
    async def play(self, file_path: str, volume: int = 100) -> None:
        """Ses dosyası çal."""

    @abstractmethod
    async def stop(self) -> None:
        """Çalmayı durdur."""

    @abstractmethod
    def is_playing(self) -> bool:
        """Şu anda ses çalıyor mu?"""

    @abstractmethod
    async def set_volume(self, volume: int) -> None:
        """Ses seviyesini ayarla (0-100)."""


class SettingsRepositoryPort(ABC):
    """Ayarlar deposu arayüzü (port)."""

    @abstractmethod
    async def load(self) -> PrayerSettings:
        """Ayarları yükle."""

    @abstractmethod
    async def save(self, settings: PrayerSettings) -> None:
        """Ayarları kaydet."""


class SchedulerPort(ABC):
    """Zamanlayıcı arayüzü (port)."""

    @abstractmethod
    def schedule_at(
        self,
        run_time: datetime,
        callback: Callable[[], None],
        job_id: str,
    ) -> None:
        """Belirtilen zamanda çalıştırılacak iş planla."""

    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """Planlanmış işi iptal et."""

    @abstractmethod
    def cancel_all(self) -> None:
        """Tüm işleri iptal et."""

    @abstractmethod
    def get_scheduled_jobs(self) -> list[tuple[str, datetime]]:
        """Planlanmış işleri listele."""


class EventBusPort(ABC):
    """Event bus arayüzü (port)."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Event yayınla."""

    @abstractmethod
    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], None],
    ) -> None:
        """Event tipine abone ol."""


class GeocodingPort(ABC):
    """Geocoding (konum çözümleme) arayüzü."""

    @abstractmethod
    async def reverse_geocode(self, latitude: float, longitude: float) -> str:
        """Koordinatlardan şehir adı bul."""

    @abstractmethod
    async def geocode(self, city_name: str) -> Location | None:
        """Şehir adından koordinat bul."""
