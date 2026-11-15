"""Bluetooth yönetimi testleri: ayar kalıcılığı, adaptör ayrıştırma, yönetici, ezan koruması."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from vakit_pi.domain.models import Location, PrayerName, PrayerSettings
from vakit_pi.infrastructure.bluetooth import (
    BluetoothctlAdapter,
    extract_error,
    parse_info,
    strip_ansi,
)
from vakit_pi.services.adhan_service import AdhanService
from vakit_pi.services.bluetooth_manager import BluetoothManager
from vakit_pi.services.ports import (
    ActionResult,
    BluetoothDeviceInfo,
    BluetoothPort,
    SystemVolumePort,
)

MAC = "41:42:86:EF:B4:62"

SPEAKER_INFO = """Device 41:42:86:EF:B4:62 (public)
\tName: Behringer C210
\tAlias: Behringer C210
\tPaired: yes
\tTrusted: yes
\tConnected: no
\tUUID: Audio Sink                (0000110b-0000-1000-8000-00805f9b34fb)
"""


def make_settings(**overrides: object) -> PrayerSettings:
    return PrayerSettings(location=Location(41.0, 29.0, "İstanbul"), **overrides)  # type: ignore[arg-type]


class FakeBluetooth(BluetoothPort):
    """Komutları kaydeden, durumu elle yönetilen sahte adaptör."""

    def __init__(self) -> None:
        self.powered = False
        self.connected = False
        self.power_works = True
        self.connect_results: list[ActionResult] = []
        self.connect_calls: list[tuple[str, bool]] = []
        self.disconnect_calls: list[str] = []
        self.scan_result: list[BluetoothDeviceInfo] = []

    async def list_paired_devices(self) -> list[dict[str, str]]:
        return []

    async def scan(self, duration: float = 8.0) -> list[BluetoothDeviceInfo]:  # noqa: ARG002
        return self.scan_result

    async def is_powered(self) -> bool:
        return self.powered

    async def set_power(self, on: bool) -> bool:
        if self.power_works:
            self.powered = on
        return self.powered == on

    async def connect(self, mac: str, *, pair_if_needed: bool = False) -> ActionResult:
        self.connect_calls.append((mac, pair_if_needed))
        result = self.connect_results.pop(0) if self.connect_results else ActionResult(True)
        self.connected = result.success
        return result

    async def disconnect(self, mac: str) -> bool:
        self.disconnect_calls.append(mac)
        self.connected = False
        return True

    async def is_connected(self, mac: str) -> bool:  # noqa: ARG002
        return self.connected


class FakeAudio(SystemVolumePort):
    def __init__(self) -> None:
        self.sink_calls: list[str] = []

    async def set_volume(self, volume: int) -> bool:  # noqa: ARG002
        return True

    async def get_volume(self) -> int | None:
        return 50

    async def set_default_bluetooth_sink(self, mac: str) -> bool:
        self.sink_calls.append(mac)
        return True


class Harness:
    """Yönetici + sahte bağımlılıklar + bellekte tutulan ayarlar."""

    def __init__(self, settings: PrayerSettings | None = None) -> None:
        self.settings = settings or make_settings()
        self.saves = 0
        self.bt = FakeBluetooth()
        self.audio = FakeAudio()
        self.manager = BluetoothManager(
            self.bt,
            self.audio,
            get_settings=lambda: self.settings,
            update_settings=self._update,
            base_delay=0.01,
            max_delay=0.02,
            watchdog_interval=0.01,
        )

    async def _update(self, **changes: object) -> None:
        self.settings = replace(self.settings, **changes)  # type: ignore[arg-type]
        self.saves += 1


async def wait_until(predicate, limit: float = 2.0) -> None:  # type: ignore[no-untyped-def]
    async with asyncio.timeout(limit):
        while not predicate():  # noqa: ASYNC110
            await asyncio.sleep(0.005)


# ---------- ayar kalıcılığı ----------


class TestSettingsPersistence:
    def test_roundtrip_keeps_bluetooth_state(self) -> None:
        settings = make_settings(
            bluetooth_device_mac=MAC, bluetooth_enabled=True, bluetooth_want_connected=False
        )
        restored = PrayerSettings.from_dict(settings.to_dict())
        assert restored.bluetooth_device_mac == MAC
        assert restored.bluetooth_enabled is True
        assert restored.bluetooth_want_connected is False

    def test_legacy_file_with_mac_keeps_auto_connect(self) -> None:
        data = make_settings(bluetooth_device_mac=MAC).to_dict()
        del data["bluetooth_enabled"]
        del data["bluetooth_want_connected"]
        restored = PrayerSettings.from_dict(data)
        assert restored.bluetooth_enabled is True
        assert restored.bluetooth_want_connected is True

    def test_legacy_file_without_mac_stays_off(self) -> None:
        data = make_settings().to_dict()
        del data["bluetooth_enabled"]
        del data["bluetooth_want_connected"]
        restored = PrayerSettings.from_dict(data)
        assert restored.bluetooth_enabled is False
        assert restored.bluetooth_want_connected is False


# ---------- adaptör ayrıştırma ----------


class TestParsing:
    def test_strip_ansi(self) -> None:
        assert strip_ansi("\x1b[0;94mConnected: yes\x1b[0m") == "Connected: yes"

    def test_parse_info_for_audio_speaker(self) -> None:
        info = parse_info(SPEAKER_INFO)
        assert info == {"name": "Behringer C210", "paired": True, "connected": False, "audio": True}

    def test_parse_info_unpaired_non_audio(self) -> None:
        info = parse_info("Device AA:BB:CC:DD:EE:FF (random)\n\tPaired: no\n\tConnected: no\n")
        assert info["paired"] is False
        assert info["audio"] is False

    def test_extract_error_prefers_failure_line(self) -> None:
        out = "Attempting to connect to X\nFailed to connect: org.bluez.Error.Failed\n"
        assert extract_error(out) == "Failed to connect: org.bluez.Error.Failed"

    def test_extract_error_ignores_prompt_lines(self) -> None:
        out = "Attempting to connect to X\n[bluetooth]# quit\n[bluetooth]#"
        assert extract_error(out) == "Attempting to connect to X"

    def test_extract_error_on_prompt_only_output(self) -> None:
        assert "çıktı vermedi" in extract_error("[bluetooth]# quit\n[bluetooth]#")

    def test_extract_error_on_empty_output(self) -> None:
        assert "çıktı vermedi" in extract_error("")


class TestAdapterConnect:
    @pytest.fixture
    def adapter(self) -> BluetoothctlAdapter:
        adapter = BluetoothctlAdapter()
        adapter._run_command = AsyncMock(return_value=(0, ""))  # type: ignore[method-assign]
        adapter._run_piped = AsyncMock(return_value=(0, ""))  # type: ignore[method-assign]
        return adapter

    async def test_unpaired_device_is_not_connected_without_pair_flag(
        self, adapter: BluetoothctlAdapter
    ) -> None:
        adapter._run_command.return_value = (0, "Device X\n\tPaired: no\n\tConnected: no\n")
        result = await adapter.connect(MAC)
        assert result.success is False
        assert "eşleşmemiş" in result.message
        adapter._run_piped.assert_not_called()

    async def test_pair_failure_reports_bluetoothctl_error(
        self, adapter: BluetoothctlAdapter
    ) -> None:
        async def run(*args: str, cmd_timeout: float = 10.0) -> tuple[int, str]:  # noqa: ARG001
            if "pair" in args:
                return 1, "Failed to pair: org.bluez.Error.AuthenticationFailed"
            return 0, "Device X\n\tPaired: no\n\tConnected: no\n"

        adapter._run_command = AsyncMock(side_effect=run)  # type: ignore[method-assign]
        result = await adapter.connect(MAC, pair_if_needed=True)
        assert result.success is False
        assert "AuthenticationFailed" in result.message

    async def test_connect_failure_reports_reason(
        self, adapter: BluetoothctlAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        async def run(*args: str, cmd_timeout: float = 10.0) -> tuple[int, str]:  # noqa: ARG001
            if "connect" in args:
                return 1, "Attempting to connect to X\nFailed to connect: org.bluez.Error.Failed"
            return 0, SPEAKER_INFO

        adapter._run_command = AsyncMock(side_effect=run)  # type: ignore[method-assign]
        result = await adapter.connect(MAC)
        assert result.success is False
        assert "org.bluez.Error.Failed" in result.message
        adapter._run_piped.assert_not_called()  # quit hata metnini yutmasın


# ---------- yönetici ----------


class TestManager:
    async def test_connect_saves_state_and_sets_sink(self) -> None:
        h = Harness()
        result = await h.manager.connect(MAC)
        try:
            assert result.success
            assert h.bt.connect_calls[0] == (MAC, True)  # eşleştirme izniyle
            assert h.audio.sink_calls[0] == MAC
            assert h.settings.bluetooth_device_mac == MAC
            assert h.settings.bluetooth_enabled is True
            assert h.settings.bluetooth_want_connected is True
        finally:
            await h.manager.stop()

    async def test_failed_connect_does_not_change_saved_state(self) -> None:
        h = Harness()
        h.bt.connect_results = [ActionResult(False, "Failed to connect")]
        result = await h.manager.connect(MAC)
        assert result.success is False
        assert h.settings.bluetooth_device_mac is None
        assert h.settings.bluetooth_want_connected is False
        assert h.saves == 0
        assert (await h.manager.status()).last_error == "Failed to connect"

    async def test_disconnect_clears_intent_but_keeps_device(self) -> None:
        h = Harness(
            make_settings(
                bluetooth_device_mac=MAC, bluetooth_enabled=True, bluetooth_want_connected=True
            )
        )
        h.bt.powered = h.bt.connected = True
        result = await h.manager.disconnect()
        assert result.success
        assert h.bt.disconnect_calls == [MAC]
        assert h.settings.bluetooth_want_connected is False
        assert h.settings.bluetooth_device_mac == MAC

    async def test_set_enabled_false_disconnects_and_powers_off(self) -> None:
        h = Harness(
            make_settings(
                bluetooth_device_mac=MAC, bluetooth_enabled=True, bluetooth_want_connected=True
            )
        )
        h.bt.powered = h.bt.connected = True
        result = await h.manager.set_enabled(False)
        assert result.success
        assert h.bt.powered is False
        assert h.settings.bluetooth_enabled is False
        assert h.settings.bluetooth_want_connected is True  # tekrar açılınca aynı cihaza dönülür

    async def test_set_enabled_reports_power_failure(self) -> None:
        h = Harness()
        h.bt.power_works = False
        result = await h.manager.set_enabled(True)
        assert result.success is False
        assert h.settings.bluetooth_enabled is False

    async def test_startup_reconnects_when_enabled_and_wanted(self) -> None:
        h = Harness(
            make_settings(
                bluetooth_device_mac=MAC, bluetooth_enabled=True, bluetooth_want_connected=True
            )
        )
        h.bt.connect_results = [ActionResult(False, "kapalı"), ActionResult(False, "kapalı")]
        await h.manager.start()
        try:
            await wait_until(lambda: h.bt.connected)
            assert len(h.bt.connect_calls) == 3  # iki başarısız + bir başarılı: vazgeçmez
            assert all(not pair for _mac, pair in h.bt.connect_calls)  # otomatik: eşleştirme yok
            await wait_until(lambda: h.audio.sink_calls == [MAC])
        finally:
            await h.manager.stop()

    async def test_startup_does_nothing_when_bluetooth_was_off(self) -> None:
        h = Harness(make_settings(bluetooth_device_mac=MAC, bluetooth_want_connected=True))
        await h.manager.start()
        await asyncio.sleep(0.05)
        assert h.bt.connect_calls == []
        assert h.bt.powered is False

    async def test_startup_does_nothing_after_manual_disconnect(self) -> None:
        h = Harness(make_settings(bluetooth_device_mac=MAC, bluetooth_enabled=True))
        await h.manager.start()
        await asyncio.sleep(0.05)
        assert h.bt.connect_calls == []
        assert h.bt.powered is True  # Bluetooth açık kalır, sadece bağlanmaz

    async def test_watchdog_reconnects_after_speaker_power_cycle(self) -> None:
        h = Harness(
            make_settings(
                bluetooth_device_mac=MAC, bluetooth_enabled=True, bluetooth_want_connected=True
            )
        )
        h.bt.connected = True
        await h.manager.start()
        try:
            await wait_until(lambda: h.audio.sink_calls == [MAC])
            h.bt.connected = False  # hoparlör kapandı
            await wait_until(lambda: len(h.audio.sink_calls) == 2)  # tekrar bağlanıp sink ayarlandı
            assert h.bt.connected
        finally:
            await h.manager.stop()

    async def test_scan_powers_on_without_persisting(self) -> None:
        h = Harness()
        h.bt.scan_result = [BluetoothDeviceInfo(MAC, "Behringer C210", False, False, True)]
        devices = await h.manager.scan()
        assert devices[0].mac == MAC
        assert h.bt.powered is True
        assert h.saves == 0

    async def test_output_ready_rules(self) -> None:
        # Bluetooth kullanılmıyor → yerel çıkış serbest
        assert await Harness().manager.output_ready() is True

        h = Harness(
            make_settings(
                bluetooth_device_mac=MAC, bluetooth_enabled=True, bluetooth_want_connected=True
            )
        )
        h.bt.connected = False
        assert await h.manager.output_ready() is False
        h.bt.connected = True
        assert await h.manager.output_ready() is True


# ---------- ezan koruması ----------


class TestAdhanGuard:
    def make_service(self, output_ready: object) -> tuple[AdhanService, MagicMock]:
        player = MagicMock()
        player.play = AsyncMock()
        player.is_playing.return_value = False
        service = AdhanService(
            audio_player=player,
            settings=make_settings(),
            output_ready=output_ready,  # type: ignore[arg-type]
        )
        service.get_adhan_path = MagicMock(return_value=MagicMock(exists=lambda: True))  # type: ignore[method-assign]
        return service, player

    async def test_skips_playback_and_logs_when_speaker_disconnected(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        service, player = self.make_service(AsyncMock(return_value=False))
        with caplog.at_level("WARNING"):
            await service.play_adhan(PrayerName.DHUHR)
        player.play.assert_not_called()
        assert "Bluetooth hoparlör bağlı değil" in caplog.text

    async def test_plays_when_speaker_connected(self) -> None:
        service, player = self.make_service(AsyncMock(return_value=True))
        await service.play_adhan(PrayerName.DHUHR)
        player.play.assert_awaited_once()

    async def test_plays_when_check_itself_fails(self) -> None:
        service, player = self.make_service(AsyncMock(side_effect=RuntimeError("boom")))
        await service.play_adhan(PrayerName.DHUHR)
        player.play.assert_awaited_once()
