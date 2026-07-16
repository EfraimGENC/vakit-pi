"""System-level volume control via PulseAudio (pactl)."""

import asyncio
import logging
import re
import shutil

from vakit_pi.services.ports import SystemVolumePort

logger = logging.getLogger(__name__)


class PulseAudioVolumeAdapter(SystemVolumePort):
    """PulseAudio üzerinden sistem ses seviyesi kontrolü.

    pactl ile default sink'in ses seviyesini ayarlar.
    Bu seviye Bluetooth hoparlör dahil tüm ses çıkışlarını etkiler
    ve reboot'a dayanır (PulseAudio ayarları kalıcıdır).
    """

    async def _run_pactl(self, *args: str) -> tuple[int, str]:
        """pactl komutu çalıştır."""
        if shutil.which("pactl") is None:
            logger.warning("pactl bulunamadı. pulseaudio-utils kurulu mu?")
            return -1, ""

        cmd = ["pactl", *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            output = stdout.decode().strip()
            if proc.returncode != 0:
                err = stderr.decode().strip()
                logger.warning(f"pactl hatası (rc={proc.returncode}): {err}")
            return proc.returncode or 0, output
        except TimeoutError:
            logger.warning(f"pactl zaman aşımı: {' '.join(cmd)}")
            return -1, ""
        except FileNotFoundError:
            logger.error("pactl bulunamadı.")
            return -1, ""

    async def set_volume(self, volume: int) -> bool:
        """Sistem ses seviyesini ayarla (0-100)."""
        if not 0 <= volume <= 100:
            raise ValueError(f"Geçersiz ses seviyesi: {volume}")

        logger.info(f"Sistem ses seviyesi ayarlanıyor: {volume}%")

        rc, _ = await self._run_pactl("set-sink-volume", "@DEFAULT_SINK@", f"{volume}%")
        if rc != 0:
            logger.error(f"Sistem ses seviyesi ayarlanamadı: {volume}%")
            return False

        logger.info(f"Sistem ses seviyesi ayarlandı: {volume}%")
        return True

    async def get_volume(self) -> int | None:
        """Mevcut sistem ses seviyesini oku (0-100)."""
        rc, output = await self._run_pactl("get-sink-volume", "@DEFAULT_SINK@")
        if rc != 0:
            return None

        # pactl çıktısı: "Volume: front-left: 52428 /  80% / ..."
        match = re.search(r"(\d+)%", output)
        if match:
            return int(match.group(1))

        return None
