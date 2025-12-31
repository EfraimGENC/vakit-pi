"""JSON-based settings repository."""

import json
import logging
from pathlib import Path

import aiofiles
import aiofiles.os

from vakit_pi.domain.models import Location, PrayerSettings
from vakit_pi.services.ports import SettingsRepositoryPort

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_PATH = Path.home() / ".config" / "vakit-pi" / "settings.json"


class JsonSettingsRepository(SettingsRepositoryPort):
    """JSON dosyasında ayarları saklayan repository."""

    def __init__(self, file_path: Path | None = None) -> None:
        """
        Initialize repository.

        Args:
            file_path: Ayar dosyası yolu (varsayılan: ~/.config/vakit-pi/settings.json)
        """
        self._file_path = file_path or DEFAULT_SETTINGS_PATH

    @property
    def file_path(self) -> Path:
        """Ayar dosyası yolu."""
        return self._file_path

    async def _ensure_dir(self) -> None:
        """Dizinin var olduğundan emin ol."""
        parent = self._file_path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ayar dizini oluşturuldu: {parent}")

    async def load(self) -> PrayerSettings:
        """Ayarları yükle."""
        if not self._file_path.exists():
            logger.info("Ayar dosyası bulunamadı, varsayılan ayarlar kullanılıyor.")
            return self._get_default_settings()

        try:
            async with aiofiles.open(self._file_path, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                logger.info(f"Ayarlar yüklendi: {self._file_path}")
                return PrayerSettings.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Ayar dosyası geçersiz JSON: {e}")
            return self._get_default_settings()
        except Exception as e:
            logger.error(f"Ayarlar yüklenirken hata: {e}")
            return self._get_default_settings()

    async def save(self, settings: PrayerSettings) -> None:
        """Ayarları kaydet."""
        await self._ensure_dir()

        try:
            data = settings.to_dict()
            async with aiofiles.open(self._file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
            logger.info(f"Ayarlar kaydedildi: {self._file_path}")
        except Exception as e:
            logger.error(f"Ayarlar kaydedilirken hata: {e}")
            raise

    def _get_default_settings(self) -> PrayerSettings:
        """Varsayılan ayarlar."""
        return PrayerSettings(
            location=Location(
                latitude=41.0082,  # İstanbul
                longitude=28.9784,
                city="İstanbul",
            )
        )

    async def exists(self) -> bool:
        """Ayar dosyası var mı?"""
        return self._file_path.exists()

    async def delete(self) -> bool:
        """Ayar dosyasını sil."""
        if self._file_path.exists():
            await aiofiles.os.remove(self._file_path)
            logger.info(f"Ayar dosyası silindi: {self._file_path}")
            return True
        return False
