"""Bluetooth device management via bluetoothctl."""

import asyncio
import logging
import re

from vakit_pi.services.ports import ActionResult, BluetoothDeviceInfo, BluetoothPort

logger = logging.getLogger(__name__)

# MAC adresi regex pattern
MAC_PATTERN = re.compile(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})")

# bluetoothctl çıktısındaki renk/kontrol kodları (ör. "\x1b[0;94m")
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x01|\x02")

# bluetoothctl interaktif istem satırları: "[bluetooth]#", "[bluetooth]# quit", "[CHG] ..." değil
PROMPT_LINE_PATTERN = re.compile(r"^\[[^\]]*\]#(\s+\w+)?\s*$")

# A2DP sink servisi: hoparlör/kulaklık gibi ses çıkışı cihazlarının işareti
AUDIO_SINK_MARKERS = ("audio sink", "0000110b")

PAIR_TIMEOUT = 35.0
CONNECT_TIMEOUT = 20.0


def strip_ansi(text: str) -> str:
    """bluetoothctl çıktısından renk kodlarını temizle."""
    return ANSI_PATTERN.sub("", text)


def extract_error(output: str) -> str:
    """bluetoothctl çıktısından kullanıcıya gösterilecek hata satırını çıkar."""
    lines = [
        line.strip()
        for line in strip_ansi(output).splitlines()
        if line.strip() and not PROMPT_LINE_PATTERN.match(line.strip())
    ]
    for line in reversed(lines):
        lowered = line.lower()
        if "failed" in lowered or "error" in lowered or "not available" in lowered:
            return line
    return lines[-1] if lines else "bluetoothctl çıktı vermedi"


def parse_info(output: str) -> dict[str, str | bool]:
    """`bluetoothctl info` çıktısını ayrıştır."""
    text = strip_ansi(output)
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition(":")
        if sep and key and key not in fields:
            fields[key.strip()] = value.strip()

    lowered = text.lower()
    return {
        "name": fields.get("Alias") or fields.get("Name") or "",
        "paired": fields.get("Paired", "no").lower() == "yes",
        "connected": fields.get("Connected", "no").lower() == "yes",
        "audio": any(marker in lowered for marker in AUDIO_SINK_MARKERS),
    }


def _is_placeholder_name(name: str, mac: str) -> bool:
    """Adı olmayan cihazlar bluetoothctl'de MAC'in tireli hali olarak görünür."""
    return not name or name.replace("-", ":").upper() == mac.upper()


class BluetoothctlAdapter(BluetoothPort):
    """bluetoothctl komutu üzerinden Bluetooth cihaz yönetimi."""

    async def _run_command(self, *args: str, cmd_timeout: float = 10.0) -> tuple[int, str]:
        """bluetoothctl komutu çalıştır ve çıktısını döndür."""
        cmd = ["bluetoothctl", *args]
        logger.debug(f"Bluetooth komutu: {' '.join(cmd)}")

        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=cmd_timeout)
            output = strip_ansi(stdout.decode(errors="replace")).strip()

            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                logger.warning(f"bluetoothctl hatası (rc={proc.returncode}): {err}")

            return proc.returncode or 0, output
        except TimeoutError:
            logger.warning(f"bluetoothctl zaman aşımı: {' '.join(cmd)}")
            if proc is not None:
                proc.kill()
                await proc.wait()
            return -1, ""
        except FileNotFoundError:
            logger.error("bluetoothctl bulunamadı. bluez paketi kurulu mu?")
            return -1, ""

    async def _run_piped(self, bt_command: str, cmd_timeout: float = 15.0) -> tuple[int, str]:
        """bluetoothctl'e stdin üzerinden komut gönder (interactive mod desteği)."""
        logger.debug(f"Bluetooth pipe komutu: {bt_command}")

        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await asyncio.wait_for(
                proc.communicate(input=f"{bt_command}\nquit\n".encode()),
                timeout=cmd_timeout,
            )
            output = strip_ansi(stdout.decode(errors="replace")).strip()
            logger.debug(f"Bluetooth pipe çıktısı: {output[:200]}")
            return proc.returncode or 0, output
        except TimeoutError:
            logger.warning(f"bluetoothctl pipe zaman aşımı: {bt_command}")
            if proc is not None:
                proc.kill()
                await proc.wait()
            return -1, ""
        except FileNotFoundError:
            logger.error("bluetoothctl bulunamadı. bluez paketi kurulu mu?")
            return -1, ""

    async def _get_info(self, mac: str) -> dict[str, str | bool] | None:
        """Cihaz bilgisi; BlueZ cihazı tanımıyorsa None."""
        rc, output = await self._run_command("info", mac)
        if rc != 0 or "not available" in output.lower():
            return None
        return parse_info(output)

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

    async def scan(self, duration: float = 8.0) -> list[BluetoothDeviceInfo]:
        """Yakındaki cihazları tara; ses cihazları ve eşleşmişler önce gelir."""
        logger.info(f"Bluetooth taraması başlıyor ({duration:.0f}s)")
        await self._run_command(
            "--timeout", str(int(duration)), "scan", "on", cmd_timeout=duration + 5.0
        )

        _rc, output = await self._run_command("devices")
        found: list[BluetoothDeviceInfo] = []
        for line in output.splitlines():
            match = MAC_PATTERN.search(line)
            if not match:
                continue
            mac = match.group(1)
            info = await self._get_info(mac)
            if info is None:
                continue
            raw_name = line.split(mac, 1)[-1].strip()
            name = str(info["name"]) or raw_name
            paired = bool(info["paired"])
            # Adı olmayan, eşleşmemiş cihazlar (çoğunlukla BLE gürültüsü) listeyi kirletir.
            if not paired and _is_placeholder_name(name, mac):
                continue
            found.append(
                BluetoothDeviceInfo(
                    mac=mac,
                    name=name or mac,
                    paired=paired,
                    connected=bool(info["connected"]),
                    audio=bool(info["audio"]),
                )
            )

        found.sort(key=lambda d: (not d.audio, not d.paired, d.name.lower()))
        logger.info(f"Bluetooth taraması bitti: {len(found)} cihaz")
        return found

    async def is_powered(self) -> bool:
        """Bluetooth adaptörü açık mı?"""
        rc, output = await self._run_command("show")
        if rc != 0:
            return False
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("Powered:"):
                return "yes" in stripped.lower()
        return False

    async def set_power(self, on: bool) -> bool:
        """Bluetooth adaptörünü aç/kapat."""
        await self._run_command("power", "on" if on else "off", cmd_timeout=8.0)
        return await self.is_powered() == on

    async def connect(self, mac: str, *, pair_if_needed: bool = False) -> ActionResult:
        """Bluetooth cihaza bağlan (gerekirse önce eşleştir)."""
        logger.info(f"Bluetooth bağlantısı deneniyor: {mac}")

        if await self.is_connected(mac):
            return ActionResult(True, "Zaten bağlı.")

        info = await self._get_info(mac)
        if info is None or not info["paired"]:
            if not pair_if_needed:
                return ActionResult(
                    False,
                    "Cihaz eşleşmemiş. Hoparlörü eşleşme moduna alıp arayüzden tarayarak seçin.",
                )
            logger.info(f"Bluetooth eşleştiriliyor: {mac}")
            _rc, pair_out = await self._run_command(
                "--agent", "NoInputNoOutput", "pair", mac, cmd_timeout=PAIR_TIMEOUT
            )
            logger.info(f"Bluetooth pair çıktısı: {pair_out[:300]}")
            info = await self._get_info(mac)
            if info is None or not info["paired"]:
                return ActionResult(False, f"Eşleştirme başarısız: {extract_error(pair_out)}")

        # Trust: cihaz kapanıp açılınca kendiliğinden yeniden bağlanabilsin
        await self._run_command("trust", mac, cmd_timeout=5.0)

        # Tek seferlik komut: bağlantı sonuçlanana kadar bekler ve gerçek sonucu ya da
        # hatayı yazar. Eskiden komut stdin'e pipe'lanıp hemen ardından çıkış gönderiliyordu;
        # çıkış bağlantı bitmeden çalışıp hata metnini yutuyordu.
        _rc, output = await self._run_command("connect", mac, cmd_timeout=CONNECT_TIMEOUT)
        logger.info(f"Bluetooth connect çıktısı: {output[:300]}")

        # Bağlantı sonrası gerçek durumu kontrol et (çıktı parse etmek yerine)
        await asyncio.sleep(1)
        if await self.is_connected(mac):
            logger.info(f"Bluetooth bağlantısı başarılı: {mac}")
            return ActionResult(True, "Bağlandı.")

        reason = extract_error(output)
        logger.warning(f"Bluetooth bağlantısı başarısız: {mac} — {reason}")
        return ActionResult(False, reason)

    async def disconnect(self, mac: str) -> bool:
        """Bluetooth bağlantısını kes."""
        logger.info(f"Bluetooth bağlantısı kesiliyor: {mac}")

        await self._run_piped(f"disconnect {mac}", cmd_timeout=10.0)

        await asyncio.sleep(1)
        still_connected = await self.is_connected(mac)

        if not still_connected:
            logger.info(f"Bluetooth bağlantısı kesildi: {mac}")
        else:
            logger.warning(f"Bluetooth bağlantı kesme başarısız: {mac}")

        return not still_connected

    async def remove(self, mac: str) -> bool:
        """Cihazı ve eşleşme kaydını sil."""
        logger.info(f"Bluetooth cihaz siliniyor: {mac}")
        _rc, output = await self._run_command("remove", mac, cmd_timeout=10.0)
        logger.info(f"Bluetooth remove çıktısı: {output[:200]}")

        # BlueZ cihazı artık tanımıyorsa silme tamamdır
        removed = await self._get_info(mac) is None
        if not removed:
            logger.warning(f"Bluetooth cihaz silinemedi: {mac} — {extract_error(output)}")
        return removed

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
