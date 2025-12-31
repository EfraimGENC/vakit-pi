"""Audio player implementations for Raspberry Pi."""

import asyncio
import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from vakit_pi.services.ports import AudioPlayerPort

logger = logging.getLogger(__name__)


class BaseAudioPlayer(AudioPlayerPort, ABC):
    """Base class for audio players."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._current_volume: int = 100

    @abstractmethod
    def _get_command(self, file_path: str, volume: int) -> list[str]:
        """Çalma komutu oluştur."""

    @abstractmethod
    def _is_available(self) -> bool:
        """Player kullanılabilir mi?"""

    async def play(self, file_path: str, volume: int = 100) -> None:
        """Ses dosyası çal ve bitmesini bekle."""
        await self._start_playback(file_path, volume)
        await self._wait_for_completion()

    async def _start_playback(self, file_path: str, volume: int = 100) -> None:
        """Ses dosyasını çalmaya başla (beklemeden)."""
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Ses dosyası bulunamadı: {file_path}")

        if not self._is_available():
            raise RuntimeError(f"{self.__class__.__name__} kullanılamıyor")

        # Önceki çalmayı durdur
        await self.stop()

        self._current_volume = volume
        cmd = self._get_command(file_path, volume)

        logger.info(f"Ses çalma başlatılıyor: {' '.join(cmd)}")

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info(f"Ses process başlatıldı: PID={self._process.pid}")

    async def _wait_for_completion(self) -> None:
        """Çalmanın bitmesini bekle."""
        if self._process is None:
            return

        _, stderr = await self._process.communicate()

        if self._process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else ""
            logger.warning(
                f"Player çıkış kodu: {self._process.returncode}, hata: {error_msg}"
            )

        self._process = None

    async def stop(self) -> None:
        """Çalmayı durdur."""
        if self._process is not None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
            except ProcessLookupError:
                pass  # Zaten sonlanmış
            finally:
                self._process = None

    def is_playing(self) -> bool:
        """Şu anda ses çalıyor mu?"""
        return self._process is not None and self._process.returncode is None

    async def set_volume(self, volume: int) -> None:
        """Ses seviyesini ayarla (0-100)."""
        if not 0 <= volume <= 100:
            raise ValueError(f"Geçersiz ses seviyesi: {volume}")
        self._current_volume = volume


class Mpg123Player(BaseAudioPlayer):
    """mpg123 ile ses çalma."""

    def _is_available(self) -> bool:
        """mpg123 kurulu mu?"""
        return shutil.which("mpg123") is not None

    def _get_command(self, file_path: str, volume: int) -> list[str]:
        """mpg123 komutu oluştur."""
        # mpg123 volume: 0-32768, biz 0-100 kullanıyoruz
        scaled_volume = int((volume / 100) * 32768)
        return [
            "mpg123",
            "--quiet",
            "--scale",
            str(scaled_volume),
            file_path,
        ]


class AplayPlayer(BaseAudioPlayer):
    """aplay (ALSA) ile ses çalma - WAV dosyaları için."""

    def _is_available(self) -> bool:
        """aplay kurulu mu?"""
        return shutil.which("aplay") is not None

    def _get_command(self, file_path: str, volume: int) -> list[str]:  # noqa: ARG002
        """aplay komutu oluştur."""
        # aplay volume kontrolü amixer ile yapılır, burada sadece çalma
        return ["aplay", "-q", file_path]

    async def set_volume(self, volume: int) -> None:
        """ALSA mixer ile ses seviyesi ayarla."""
        await super().set_volume(volume)

        if shutil.which("amixer") is not None:
            proc = await asyncio.create_subprocess_exec(
                "amixer",
                "set",
                "Master",
                f"{volume}%",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()


class FfplayPlayer(BaseAudioPlayer):
    """ffplay (FFmpeg) ile ses çalma."""

    def _is_available(self) -> bool:
        """ffplay kurulu mu?"""
        return shutil.which("ffplay") is not None

    def _get_command(self, file_path: str, volume: int) -> list[str]:
        """ffplay komutu oluştur."""
        # ffplay volume: 0.0-1.0
        scaled_volume = volume / 100
        return [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-volume",
            str(int(scaled_volume * 100)),
            "-loglevel",
            "quiet",
            file_path,
        ]


class PulseAudioPlayer(BaseAudioPlayer):
    """paplay (PulseAudio) ile ses çalma."""

    def _is_available(self) -> bool:
        """paplay kurulu mu?"""
        return shutil.which("paplay") is not None

    def _get_command(self, file_path: str, volume: int) -> list[str]:
        """paplay komutu oluştur."""
        # paplay volume: 0-65536
        scaled_volume = int((volume / 100) * 65536)
        return [
            "paplay",
            f"--volume={scaled_volume}",
            file_path,
        ]


def get_best_player() -> BaseAudioPlayer:
    """Sistemde mevcut en iyi player'ı döndür."""
    players: list[tuple[str, type[BaseAudioPlayer]]] = [
        ("mpg123", Mpg123Player),  # MP3 için en iyi
        ("ffplay", FfplayPlayer),  # Çok formatlı
        ("paplay", PulseAudioPlayer),  # PulseAudio varsa
        ("aplay", AplayPlayer),  # ALSA, sadece WAV
    ]

    for name, player_class in players:
        if shutil.which(name) is not None:
            logger.info(f"Ses oynatıcı seçildi: {name}")
            return player_class()

    raise RuntimeError(
        "Hiçbir ses oynatıcı bulunamadı. mpg123, ffplay, paplay veya aplay kurulu olmalı."
    )
