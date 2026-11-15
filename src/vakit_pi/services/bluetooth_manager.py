"""Bluetooth hoparlör yönetimi: aç/kapat, tara, bağlan ve kalıcı durumu koru.

Kalıcı durum `PrayerSettings` içinde tutulur:
- ``bluetooth_enabled``: Bluetooth açık mı
- ``bluetooth_device_mac``: son seçilen hoparlör
- ``bluetooth_want_connected``: o hoparlöre bağlı kalınmak isteniyor mu

Açılışta (elektrik kesintisi sonrası dahil) Bluetooth açık ve bağlı kalma niyeti varsa
hoparlöre süresiz olarak yeniden bağlanılır. Kullanıcı bağlantıyı kendisi keserse
bu niyet temizlenir; elektrik gelince kendiliğinden bağlanılmaz.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from vakit_pi.domain.models import PrayerSettings
from vakit_pi.services.ports import (
    ActionResult,
    BluetoothDeviceInfo,
    BluetoothPort,
    SystemVolumePort,
)

logger = logging.getLogger(__name__)

SettingsGetter = Callable[[], PrayerSettings]
SettingsUpdater = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class BluetoothStatus:
    """Arayüze gösterilecek anlık Bluetooth durumu."""

    enabled: bool
    powered: bool
    device_mac: str | None
    want_connected: bool
    connected: bool
    last_error: str | None


class BluetoothManager:
    """Bluetooth açık/kapalı, seçili hoparlör ve otomatik yeniden bağlanmayı yönetir."""

    def __init__(
        self,
        bluetooth: BluetoothPort,
        audio: SystemVolumePort,
        get_settings: SettingsGetter,
        update_settings: SettingsUpdater,
        *,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        watchdog_interval: float = 30.0,
    ) -> None:
        """
        Initialize manager.

        Args:
            bluetooth: Bluetooth adaptörü
            audio: Varsayılan ses çıkışını ayarlayan adaptör
            get_settings: Güncel ayarları döndürür
            update_settings: Ayar alanlarını değiştirip diske kaydeder (``**changes``)
            base_delay: Yeniden bağlanma için ilk bekleme (sn); her denemede iki katına çıkar
            max_delay: Yeniden bağlanma beklemesinin üst sınırı (sn)
            watchdog_interval: Bağlıyken bağlantının kontrol sıklığı (sn)
        """
        self._bluetooth = bluetooth
        self._audio = audio
        self._get_settings = get_settings
        self._update_settings = update_settings
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._watchdog_interval = watchdog_interval
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._last_error: str | None = None

    # ---------- yaşam döngüsü ----------

    async def start(self) -> None:
        """Uygulama açılışı: kayıtlı son duruma göre Bluetooth'u toparla."""
        settings = self._get_settings()
        if not settings.bluetooth_enabled:
            logger.info("Bluetooth kapalı (kayıtlı durum), otomatik bağlanma yok.")
            return

        logger.info("Bluetooth açık (kayıtlı durum), toparlanıyor...")
        await self._bluetooth.set_power(True)
        self._ensure_supervisor()

    async def stop(self) -> None:
        """Uygulama kapanışı: arka plan görevini durdur."""
        await self._cancel_supervisor()

    # ---------- sorgular ----------

    async def status(self) -> BluetoothStatus:
        """Anlık durum."""
        settings = self._get_settings()
        mac = settings.bluetooth_device_mac
        powered = await self._bluetooth.is_powered()
        connected = bool(mac) and powered and await self._bluetooth.is_connected(mac or "")
        return BluetoothStatus(
            enabled=settings.bluetooth_enabled,
            powered=powered,
            device_mac=mac,
            want_connected=settings.bluetooth_want_connected,
            connected=connected,
            last_error=self._last_error,
        )

    async def output_ready(self) -> bool:
        """Ezan çalınabilir mi? Bluetooth çıkışı bekleniyorsa hoparlör bağlı olmalı."""
        settings = self._get_settings()
        mac = settings.bluetooth_device_mac
        expects_bluetooth = settings.bluetooth_enabled and settings.bluetooth_want_connected
        if not expects_bluetooth or not mac:
            return True
        return await self._bluetooth.is_connected(mac)

    # ---------- kullanıcı işlemleri ----------

    async def set_enabled(self, enabled: bool) -> ActionResult:
        """Bluetooth'u aç veya kapat."""
        async with self._lock:
            await self._cancel_supervisor()
            settings = self._get_settings()
            mac = settings.bluetooth_device_mac

            if enabled:
                if not await self._bluetooth.set_power(True):
                    return ActionResult(
                        False, "Bluetooth açılamadı (rfkill engeli veya adaptör yok olabilir)."
                    )
                await self._update_settings(bluetooth_enabled=True)
                self._ensure_supervisor()
                return ActionResult(True, "Bluetooth açıldı.")

            if mac and await self._bluetooth.is_connected(mac):
                await self._bluetooth.disconnect(mac)
            await self._bluetooth.set_power(False)
            await self._update_settings(bluetooth_enabled=False)
            self._last_error = None
            return ActionResult(True, "Bluetooth kapatıldı.")

    async def scan(self, duration: float = 8.0) -> list[BluetoothDeviceInfo]:
        """Yakındaki cihazları tara. Bluetooth kapalıysa açar (kalıcı durumu değiştirmez)."""
        async with self._lock:
            if not await self._bluetooth.is_powered():
                await self._bluetooth.set_power(True)
            return await self._bluetooth.scan(duration)

    async def connect(self, mac: str) -> ActionResult:
        """Hoparlöre bağlan (gerekirse eşleştir) ve durumu kalıcı olarak kaydet."""
        async with self._lock:
            await self._cancel_supervisor()

            if not await self._bluetooth.set_power(True):
                self._ensure_supervisor()
                return ActionResult(False, "Bluetooth adaptörü açılamadı.")

            result = await self._bluetooth.connect(mac, pair_if_needed=True)
            if not result.success:
                self._last_error = result.message
                self._ensure_supervisor()  # önceki niyet varsa kaldığı yerden devam
                return result

            self._last_error = None
            await self._audio.set_default_bluetooth_sink(mac)
            await self._update_settings(
                bluetooth_enabled=True,
                bluetooth_want_connected=True,
                bluetooth_device_mac=mac,
            )
            self._ensure_supervisor()
            return result

    async def disconnect(self) -> ActionResult:
        """Bağlantıyı kes ve bağlı kalma niyetini temizle."""
        async with self._lock:
            await self._cancel_supervisor()
            await self._update_settings(bluetooth_want_connected=False)
            self._last_error = None

            mac = self._get_settings().bluetooth_device_mac
            if not mac:
                return ActionResult(True, "Kayıtlı Bluetooth cihaz yok.")
            if await self._bluetooth.disconnect(mac):
                return ActionResult(True, f"Bluetooth bağlantısı kesildi: {mac}")
            return ActionResult(False, f"Bluetooth bağlantı kesme başarısız: {mac}")

    async def remove_device(self, mac: str) -> ActionResult:
        """Eşleşmiş cihazı sil. Seçili hoparlörse bağlı kalma niyeti ve seçim de temizlenir."""
        async with self._lock:
            saved_mac = self._get_settings().bluetooth_device_mac
            is_selected = bool(saved_mac) and (saved_mac or "").upper() == mac.upper()

            if is_selected:
                await self._cancel_supervisor()
            if await self._bluetooth.is_connected(mac):
                await self._bluetooth.disconnect(mac)

            if not await self._bluetooth.remove(mac):
                if is_selected:
                    self._ensure_supervisor()  # silinemedi: önceki niyetle devam
                return ActionResult(False, f"Cihaz silinemedi: {mac}")

            if is_selected:
                await self._update_settings(
                    bluetooth_device_mac=None, bluetooth_want_connected=False
                )
                self._last_error = None
            return ActionResult(True, f"Eşleşme silindi: {mac}")

    # ---------- arka plan: otomatik yeniden bağlanma ----------

    def _ensure_supervisor(self) -> None:
        """Niyet varsa (açık + bağlı kalmak istiyor + cihaz seçili) görevi başlat."""
        settings = self._get_settings()
        mac = settings.bluetooth_device_mac
        if not (settings.bluetooth_enabled and settings.bluetooth_want_connected and mac):
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._supervise(mac))
            logger.info(f"Bluetooth otomatik bağlanma başlatıldı: {mac}")

    async def _cancel_supervisor(self) -> None:
        task, self._task = self._task, None
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _supervise(self, mac: str) -> None:
        """Hoparlöre bağlı kalmaya çalış; vazgeçme, üstel bekleme ile tekrar dene."""
        attempt = 0
        failed_attempts = 0
        was_connected = False
        started = time.monotonic()

        while True:
            try:
                if not await self._bluetooth.is_powered():
                    await self._bluetooth.set_power(True)

                if await self._bluetooth.is_connected(mac):
                    if not was_connected:
                        await self._audio.set_default_bluetooth_sink(mac)
                        self._last_error = None
                        was_connected = True
                        logger.info(
                            f"Bluetooth bağlandı: {mac} "
                            f"({time.monotonic() - started:.0f} sn sonra, "
                            f"{failed_attempts} başarısız deneme)"
                        )
                    attempt = 0
                    failed_attempts = 0
                    await asyncio.sleep(self._watchdog_interval)
                    continue

                was_connected = False
                logger.info(f"Bluetooth bağlantı denemesi #{attempt + 1}: {mac}")
                result = await self._bluetooth.connect(mac)
                if result.success:
                    continue  # bir sonraki turda bağlı görünüp sink ayarlanır

                self._last_error = result.message
                delay = min(self._base_delay * 2 ** min(attempt, 10), self._max_delay)
                attempt += 1
                failed_attempts += 1
                logger.info(f"Bluetooth bağlanamadı ({result.message}); {delay:.0f}s sonra tekrar")
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Bluetooth otomatik bağlanma hatası: {e}", exc_info=True)
                await asyncio.sleep(self._max_delay)
