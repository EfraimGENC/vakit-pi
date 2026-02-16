"""Bluetooth device management via bluetoothctl."""

import asyncio
import logging
import re

from vakit_pi.services.ports import BluetoothPort

logger = logging.getLogger(__name__)

# MAC adresi regex pattern
MAC_PATTERN = re.compile(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})")


class BluetoothctlAdapter(BluetoothPort):
    """bluetoothctl komutu üzerinden Bluetooth cihaz yönetimi."""

    async def _run_command(self, *args: str, cmd_timeout: float = 10.0) -> tuple[int, str]:
        """bluetoothctl komutu çalıştır ve çıktısını döndür."""
        cmd = ["bluetoothctl", *args]
        logger.debug(f"Bluetooth komutu: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=cmd_timeout)
            output = stdout.decode().strip()

            if proc.returncode != 0:
                err = stderr.decode().strip()
                logger.warning(f"bluetoothctl hatası (rc={proc.returncode}): {err}")

            return proc.returncode or 0, output
        except TimeoutError:
            logger.warning(f"bluetoothctl zaman aşımı: {' '.join(cmd)}")
            proc.kill()
            await proc.wait()
            return -1, ""
        except FileNotFoundError:
            logger.error("bluetoothctl bulunamadı. bluez paketi kurulu mu?")
            return -1, ""

    async def list_paired_devices(self) -> list[dict[str, str]]:
        """Eşleşmiş Bluetooth cihazlarını listele."""
        rc, output = await self._run_command("devices", "Paired")

        # bluetoothctl "devices Paired" desteklenmiyorsa fallback
        if rc != 0 or not output:
            rc, output = await self._run_command("devices")

        devices: list[dict[str, str]] = []
        for line in output.splitlines():
            match = MAC_PATTERN.search(line)
            if match:
                mac = match.group(1)
                # MAC adresinden sonraki kısmı isim olarak al
                name_part = line.split(mac, 1)[-1].strip()
                connected = await self.is_connected(mac)
                devices.append(
                    {
                        "mac": mac,
                        "name": name_part or mac,
                        "connected": str(connected).lower(),
                    }
                )

        return devices

    async def connect(self, mac: str) -> bool:
        """Bluetooth cihaza bağlan."""
        logger.info(f"Bluetooth bağlantısı deneniyor: {mac}")
        rc, output = await self._run_command("connect", mac, cmd_timeout=15.0)

        success = rc == 0 and "Connection successful" in output
        if success:
            logger.info(f"Bluetooth bağlantısı başarılı: {mac}")
        else:
            logger.warning(f"Bluetooth bağlantısı başarısız: {mac} — {output}")

        return success

    async def disconnect(self, mac: str) -> bool:
        """Bluetooth bağlantısını kes."""
        logger.info(f"Bluetooth bağlantısı kesiliyor: {mac}")
        rc, output = await self._run_command("disconnect", mac)

        success = rc == 0 and "Successful disconnected" in output
        if success:
            logger.info(f"Bluetooth bağlantısı kesildi: {mac}")
        else:
            logger.warning(f"Bluetooth bağlantı kesme başarısız: {mac} — {output}")

        return success

    async def is_connected(self, mac: str) -> bool:
        """Cihaz bağlı mı kontrol et."""
        rc, output = await self._run_command("info", mac)
        if rc != 0:
            return False

        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("Connected:"):
                return "yes" in stripped.lower()

        return False

    async def auto_connect_loop(
        self,
        mac: str,
        max_retries: int = 30,
        base_delay: float = 3.0,
        max_delay: float = 60.0,
    ) -> bool:
        """
        Kayıtlı Bluetooth cihaza exponential backoff ile otomatik bağlan.

        Returns:
            True: bağlantı başarılı, False: tüm denemeler tükendi
        """
        logger.info(f"Bluetooth auto-connect başlatıldı: {mac} (max {max_retries} deneme)")

        for attempt in range(1, max_retries + 1):
            # Zaten bağlı mı kontrol et
            if await self.is_connected(mac):
                logger.info(f"Bluetooth cihaz zaten bağlı: {mac}")
                return True

            # Bağlanmayı dene
            logger.info(f"Bluetooth bağlantı denemesi {attempt}/{max_retries}: {mac}")
            success = await self.connect(mac)

            if success:
                logger.info(f"Bluetooth auto-connect başarılı: {mac} (deneme {attempt})")
                return True

            # Exponential backoff
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.info(f"Bluetooth bağlantı başarısız, {delay:.0f}s sonra tekrar denenecek...")
            await asyncio.sleep(delay)

        logger.error(f"Bluetooth auto-connect başarısız: {mac} — {max_retries} deneme tükendi.")
        return False
