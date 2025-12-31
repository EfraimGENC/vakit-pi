"""Adhan (ezan) çalma servisi."""

import asyncio
import logging
from pathlib import Path

from vakit_pi.domain.events import (
    AdhanFinishedEvent,
    AdhanStartedEvent,
    AudioErrorEvent,
)
from vakit_pi.domain.models import AdhanType, PrayerName, PrayerSettings
from vakit_pi.services.ports import AudioPlayerPort, EventBusPort

logger = logging.getLogger(__name__)


class AdhanService:
    """Ezan çalma servisi."""

    def __init__(
        self,
        audio_player: AudioPlayerPort,
        settings: PrayerSettings,
        event_bus: EventBusPort | None = None,
        audio_dir: Path | None = None,
    ) -> None:
        """
        Initialize adhan service.

        Args:
            audio_player: Ses çalma adaptörü
            settings: Namaz ayarları
            event_bus: Event bus (opsiyonel)
            audio_dir: Ezan ses dosyalarının bulunduğu dizin
        """
        self._audio_player = audio_player
        self._settings = settings
        self._event_bus = event_bus
        self._audio_dir = audio_dir or Path(__file__).parent.parent / "assets" / "audio"
        self._is_playing = False

    @property
    def settings(self) -> PrayerSettings:
        """Mevcut ayarlar."""
        return self._settings

    def update_settings(self, settings: PrayerSettings) -> None:
        """Ayarları güncelle."""
        self._settings = settings

    def get_adhan_path(self, adhan_type: AdhanType | None = None) -> Path:
        """Ezan ses dosyasının yolunu döndür."""
        if adhan_type is None:
            adhan_type = self._settings.adhan_type
        return self._audio_dir / adhan_type.filename

    async def play_adhan(self, prayer: PrayerName) -> None:
        """
        Ezan çal.

        Args:
            prayer: Hangi namaz vakti için
        """
        if not self._settings.is_prayer_enabled(prayer):
            logger.info(f"{prayer.display_name} vakti için ezan devre dışı.")
            return

        if self._is_playing:
            logger.warning("Zaten bir ezan çalıyor, yeni ezan başlatılmadı.")
            return

        volume = self._settings.volume.get_volume(prayer)
        adhan_path = self.get_adhan_path()

        if not adhan_path.exists():
            error_msg = f"Ezan dosyası bulunamadı: {adhan_path}"
            logger.error(error_msg)
            if self._event_bus:
                self._event_bus.publish(AudioErrorEvent(error_message=error_msg, prayer=prayer))
            return

        try:
            self._is_playing = True
            logger.info(f"{prayer.display_name} ezanı çalınıyor (ses: {volume}%)")

            if self._event_bus:
                self._event_bus.publish(AdhanStartedEvent(prayer=prayer, volume=volume))

            await self._audio_player.play(str(adhan_path), volume=volume)

            logger.info(f"{prayer.display_name} ezanı tamamlandı.")

            if self._event_bus:
                self._event_bus.publish(AdhanFinishedEvent(prayer=prayer))

        except Exception as e:
            error_msg = f"Ezan çalınırken hata: {e}"
            logger.error(error_msg)
            if self._event_bus:
                self._event_bus.publish(AudioErrorEvent(error_message=error_msg, prayer=prayer))
        finally:
            self._is_playing = False

    async def stop_adhan(self) -> None:
        """Ezanı durdur."""
        if self._is_playing:
            await self._audio_player.stop()
            self._is_playing = False
            logger.info("Ezan durduruldu.")

    def is_playing(self) -> bool:
        """Ezan çalıyor mu?"""
        return self._is_playing

    async def test_audio(self, volume: int | None = None) -> bool:
        """
        Ses testi yap.

        Args:
            volume: Test ses seviyesi (varsayılan: ayarlardaki default)

        Returns:
            Başarılı mı?
        """
        if volume is None:
            volume = self._settings.volume.default

        adhan_path = self.get_adhan_path()
        if not adhan_path.exists():
            logger.error(f"Test için ezan dosyası bulunamadı: {adhan_path}")
            return False

        try:
            # Sadece 5 saniyelik test çal
            logger.info(f"Ses testi başlatılıyor (ses: {volume}%)")
            await self._audio_player.play(str(adhan_path), volume=volume)

            # 5 saniye sonra durdur
            await asyncio.sleep(5)
            await self._audio_player.stop()

            logger.info("Ses testi tamamlandı.")
            return True
        except Exception as e:
            logger.error(f"Ses testi başarısız: {e}")
            return False
