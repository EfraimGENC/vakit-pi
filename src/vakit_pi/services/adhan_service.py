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

    def get_adhan_path(
        self, adhan_type: AdhanType | None = None, prayer: PrayerName | None = None
    ) -> Path:
        """
        Ezan ses dosyasının yolunu döndür.

        Önce vakite özel dosya aranır (örn: adhan_istanbul_ogle.mp3),
        bulunamazsa varsayılan dosya döndürülür (örn: adhan_istanbul.mp3).

        Args:
            adhan_type: Ezan türü (None ise ayarlardan alınır)
            prayer: Namaz vakti (None ise vakite özel dosya aranmaz)

        Returns:
            Ezan ses dosyasının yolu
        """
        if adhan_type is None:
            adhan_type = self._settings.adhan_type

        # Vakite özel dosya kontrolü
        if prayer is not None:
            prayer_specific_filename = f"adhan_{adhan_type.value}_{prayer.value}.mp3"
            prayer_specific_path = self._audio_dir / prayer_specific_filename
            if prayer_specific_path.exists():
                logger.debug(
                    f"Vakite özel ezan dosyası bulundu: {prayer_specific_filename}"
                )
                return prayer_specific_path

        # Varsayılan dosya
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
        adhan_path = self.get_adhan_path(prayer=prayer)

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
        """Ezanı veya ses testini durdur."""
        if self._is_playing or self._audio_player.is_playing():
            await self._audio_player.stop()
            self._is_playing = False
            logger.info("Ses durduruldu.")

    def is_playing(self) -> bool:
        """Ezan veya ses testi çalıyor mu?"""
        return self._is_playing or self._audio_player.is_playing()

    async def test_audio(self, volume: int | None = None, duration: int = 10) -> bool:
        """
        Ses testi yap.

        Ses testi sırasında stop_adhan() ile durdurulabilir.

        Args:
            volume: Test ses seviyesi (varsayılan: ayarlardaki default)
            duration: Test süresi saniye cinsinden (varsayılan: 10)

        Returns:
            Başarılı mı?
        """
        if volume is None:
            volume = self._settings.volume.default

        adhan_path = self.get_adhan_path()
        if not adhan_path.exists():
            logger.error(f"Test için ezan dosyası bulunamadı: {adhan_path}")
            return False

        if self._is_playing:
            logger.warning("Zaten ses çalıyor, test başlatılmadı.")
            return False

        try:
            self._is_playing = True
            logger.info(f"Ses testi başlatılıyor (ses: {volume}%, süre: {duration}s)")

            # Ses çalmayı başlat (beklemeden)
            await self._audio_player._start_playback(str(adhan_path), volume=volume)

            # Belirtilen süre kadar bekle veya ses bitene kadar
            elapsed = 0
            check_interval = 0.5
            while elapsed < duration and self._audio_player.is_playing():
                await asyncio.sleep(check_interval)
                elapsed += check_interval

            # Hala çalıyorsa durdur
            if self._audio_player.is_playing():
                logger.info(f"Test süresi doldu ({duration}s), ses durduruluyor.")
                await self._audio_player.stop()

            logger.info("Ses testi tamamlandı.")
            return True
        except asyncio.CancelledError:
            logger.info("Ses testi iptal edildi.")
            await self._audio_player.stop()
            return False
        except Exception as e:
            logger.error(f"Ses testi başarısız: {e}")
            await self._audio_player.stop()
            return False
        finally:
            self._is_playing = False
