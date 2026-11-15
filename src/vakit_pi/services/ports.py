"""Service layer interfaces (ports)."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

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
        callback: Callable[[], None] | Callable[[], Coroutine[Any, Any, None]],
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


@dataclass(frozen=True)
class ActionResult:
    """Bir Bluetooth işleminin sonucu (başarı + kullanıcıya gösterilecek açıklama)."""

    success: bool
    message: str = ""


@dataclass(frozen=True)
class BluetoothDeviceInfo:
    """Taramada bulunan veya eşleşmiş Bluetooth cihazı."""

    mac: str
    name: str
    paired: bool
    connected: bool
    audio: bool  # Ses çıkışı (A2DP sink) destekliyor mu


class BluetoothPort(ABC):
    """Bluetooth cihaz yönetimi arayüzü (port)."""

    @abstractmethod
    async def list_paired_devices(self) -> list[dict[str, str]]:
        """Eşleşmiş Bluetooth cihazlarını listele."""

    @abstractmethod
    async def scan(self, duration: float = 8.0) -> list[BluetoothDeviceInfo]:
        """Yakındaki Bluetooth cihazlarını tara (eşleşmişler dahil)."""

    @abstractmethod
    async def is_powered(self) -> bool:
        """Bluetooth adaptörü açık mı?"""

    @abstractmethod
    async def set_power(self, on: bool) -> bool:
        """Bluetooth adaptörünü aç/kapat. Başarılıysa True."""

    @abstractmethod
    async def connect(self, mac: str, *, pair_if_needed: bool = False) -> ActionResult:
        """Bluetooth cihaza bağlan. pair_if_needed=True ise eşleşmemiş cihazı eşleştirir."""

    @abstractmethod
    async def disconnect(self, mac: str) -> bool:
        """Bluetooth bağlantısını kes."""

    @abstractmethod
    async def is_connected(self, mac: str) -> bool:
        """Cihaz bağlı mı?"""

    @abstractmethod
    async def remove(self, mac: str) -> bool:
        """Cihazı ve eşleşme kaydını sil. Başarılıysa (ya da zaten yoksa) True."""


class SystemVolumePort(ABC):
    """Sistem ses seviyesi arayüzü (Bluetooth hoparlör seviyesi)."""

    @abstractmethod
    async def set_volume(self, volume: int) -> bool:
        """Sistem ses seviyesini ayarla (0-100). Tüm Pi sesini etkiler."""

    @abstractmethod
    async def get_volume(self) -> int | None:
        """Mevcut sistem ses seviyesini oku (0-100)."""

    @abstractmethod
    async def set_default_bluetooth_sink(self, mac: str) -> bool:
        """Verilen Bluetooth cihazın ses çıkışını varsayılan çıkış yap."""


class GeocodingPort(ABC):
    """Geocoding (konum çözümleme) arayüzü."""

    @abstractmethod
    async def reverse_geocode(self, latitude: float, longitude: float) -> str:
        """Koordinatlardan şehir adı bul."""

    @abstractmethod
    async def geocode(self, city_name: str) -> Location | None:
        """Şehir adından koordinat bul."""
