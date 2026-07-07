"""Tests for audio anti-gate processing."""

import pytest

from vakit_pi.infrastructure import audio as audio_module
from vakit_pi.infrastructure.audio import (
    AntiGateConfig,
    FfmpegAntiGatePlayer,
    Mpg123Player,
    build_antigate_filter,
    build_tts_command,
    get_best_player,
)

ANTIGATE_ENV_VARS = [
    "VAKIT_PI_ANTIGATE",
    "VAKIT_PI_ANTIGATE_LEADIN",
    "VAKIT_PI_ANTIGATE_TONE_HZ",
    "VAKIT_PI_ANTIGATE_COMPRESS",
    "VAKIT_PI_ANTIGATE_FLOOR_DB",
    "VAKIT_PI_ANTIGATE_TAIL",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Her testte anti-gate ortam değişkenlerini temizle (izolasyon)."""
    for var in ANTIGATE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestAntiGateConfig:
    """AntiGateConfig.from_env tests."""

    def test_defaults(self) -> None:
        """Ortam değişkeni yokken makul varsayılanlar kullanılır."""
        config = AntiGateConfig.from_env()

        assert config.enabled is True
        assert config.leadin_seconds == 1.5
        assert config.tone_hz == 55
        assert config.compress is True
        assert config.floor_db is None
        assert config.tail_seconds == 2.5

    def test_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ortam değişkenleri varsayılanları ezer."""
        monkeypatch.setenv("VAKIT_PI_ANTIGATE", "0")
        monkeypatch.setenv("VAKIT_PI_ANTIGATE_LEADIN", "2.5")
        monkeypatch.setenv("VAKIT_PI_ANTIGATE_TONE_HZ", "40")
        monkeypatch.setenv("VAKIT_PI_ANTIGATE_COMPRESS", "0")
        monkeypatch.setenv("VAKIT_PI_ANTIGATE_TAIL", "3.0")

        config = AntiGateConfig.from_env()

        assert config.enabled is False
        assert config.leadin_seconds == 2.5
        assert config.tone_hz == 40
        assert config.compress is False
        assert config.tail_seconds == 3.0

    def test_floor_db_parsed_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FLOOR_DB sayısal verilince float olarak okunur."""
        monkeypatch.setenv("VAKIT_PI_ANTIGATE_FLOOR_DB", "-48")

        assert AntiGateConfig.from_env().floor_db == -48.0

    def test_floor_db_off_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FLOOR_DB 'off' verilince taban tonu kapalıdır (None)."""
        monkeypatch.setenv("VAKIT_PI_ANTIGATE_FLOOR_DB", "off")

        assert AntiGateConfig.from_env().floor_db is None


class TestBuildAntiGateFilter:
    """build_antigate_filter tests."""

    def test_leadin_adds_tone_and_concat(self) -> None:
        """Lead-in süresi > 0 iken ana sesin önüne ton concat edilir."""
        config = AntiGateConfig(leadin_seconds=1.5, tone_hz=55)

        chain = build_antigate_filter(config, volume=100)

        assert "sine=" in chain
        assert "frequency=55" in chain
        assert "concat=" in chain

    def test_no_leadin_skips_tone(self) -> None:
        """Lead-in süresi 0 iken ton/concat eklenmez."""
        config = AntiGateConfig(leadin_seconds=0.0)

        chain = build_antigate_filter(config, volume=100)

        assert "sine=" not in chain
        assert "concat=" not in chain

    def test_compress_enabled_adds_dynaudnorm(self) -> None:
        """Sıkıştırma açıkken dinamik normalizasyon eklenir."""
        chain = build_antigate_filter(AntiGateConfig(compress=True), volume=100)

        assert "dynaudnorm" in chain

    def test_compress_disabled_omits_dynaudnorm(self) -> None:
        """Sıkıştırma kapalıyken dinamik normalizasyon eklenmez."""
        chain = build_antigate_filter(AntiGateConfig(compress=False), volume=100)

        assert "dynaudnorm" not in chain

    def test_floor_disabled_omits_amix(self) -> None:
        """Taban tonu kapalıyken (None) amix eklenmez."""
        chain = build_antigate_filter(AntiGateConfig(floor_db=None), volume=100)

        assert "amix" not in chain

    def test_floor_enabled_adds_amix(self) -> None:
        """Taban tonu açıkken amix ile karıştırılır."""
        chain = build_antigate_filter(AntiGateConfig(floor_db=-48.0), volume=100)

        assert "amix" in chain

    def test_volume_applied_as_linear_gain(self) -> None:
        """Ses seviyesi 0-100 lineer kazanç olarak uygulanır."""
        chain = build_antigate_filter(AntiGateConfig(), volume=80)

        assert "volume=0.8" in chain

    def test_tail_adds_apad(self) -> None:
        """Tail > 0 iken çıkışa apad ile dolgu sessizlik eklenir.

        PulseAudio çıkış buffer'ı drain edilmediği için son ~1.5s kesiliyordu;
        apad dolgusu gerçek içeriğin sonuna kadar çalınmasını garanti eder.
        """
        chain = build_antigate_filter(AntiGateConfig(tail_seconds=2.5), volume=100)

        assert "apad=pad_dur=2.5" in chain
        # apad son aşama olmalı: çıkış etiketi apad'dan gelir
        assert chain.rstrip().endswith("[out]")
        assert "apad" in chain.rsplit("[out]", 1)[0].rsplit(";", 1)[-1]

    def test_no_tail_omits_apad(self) -> None:
        """Tail 0 iken apad eklenmez."""
        chain = build_antigate_filter(AntiGateConfig(tail_seconds=0.0), volume=100)

        assert "apad" not in chain


class TestFfmpegAntiGatePlayer:
    """FfmpegAntiGatePlayer._get_command tests."""

    def test_command_uses_ffmpeg_with_input_and_pulse_output(self) -> None:
        """Komut ffmpeg ile input dosyasını PulseAudio'ya çalar."""
        player = FfmpegAntiGatePlayer(config=AntiGateConfig())

        cmd = player._get_command("/tmp/adhan.mp3", volume=90)

        assert cmd[0] == "ffmpeg"
        assert "/tmp/adhan.mp3" in cmd
        assert "-i" in cmd
        # PulseAudio çıkışı
        assert "pulse" in cmd

    def test_command_applies_antigate_filter(self) -> None:
        """Komut anti-gate filtre zincirini ve [out] map'ini içerir."""
        config = AntiGateConfig()
        player = FfmpegAntiGatePlayer(config=config)

        cmd = player._get_command("/tmp/adhan.mp3", volume=90)

        fc_index = cmd.index("-filter_complex")
        assert cmd[fc_index + 1] == build_antigate_filter(config, volume=90)
        map_index = cmd.index("-map")
        assert cmd[map_index + 1] == "[out]"

    def test_command_reads_from_stdin_pipe(self) -> None:
        """Input olarak '-' verilince ffmpeg stdin'den (pipe) okur (TTS için)."""
        player = FfmpegAntiGatePlayer(config=AntiGateConfig())

        cmd = player._get_command("-", volume=100)

        i_index = cmd.index("-i")
        assert cmd[i_index + 1] == "pipe:0"


def _which_factory(available: set[str]):
    """Yalnızca verilen isimler için yol döndüren sahte shutil.which."""

    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in available else None

    return fake_which


class TestGetBestPlayer:
    """get_best_player seçim mantığı."""

    def test_prefers_ffmpeg_antigate_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ffmpeg mevcut ve anti-gate açıkken FfmpegAntiGatePlayer seçilir."""
        monkeypatch.setattr(audio_module.shutil, "which", _which_factory({"ffmpeg", "mpg123"}))

        player = get_best_player(AntiGateConfig(enabled=True))

        assert isinstance(player, FfmpegAntiGatePlayer)

    def test_falls_back_when_antigate_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Anti-gate kapalıyken ffmpeg olsa bile mevcut zincire düşülür."""
        monkeypatch.setattr(audio_module.shutil, "which", _which_factory({"ffmpeg", "mpg123"}))

        player = get_best_player(AntiGateConfig(enabled=False))

        assert not isinstance(player, FfmpegAntiGatePlayer)
        assert isinstance(player, Mpg123Player)

    def test_falls_back_when_ffmpeg_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ffmpeg yoksa mevcut zincire düşülür."""
        monkeypatch.setattr(audio_module.shutil, "which", _which_factory({"mpg123"}))

        player = get_best_player(AntiGateConfig(enabled=True))

        assert isinstance(player, Mpg123Player)


class TestBuildTtsCommand:
    """build_tts_command — TTS stream'ini oynatacak komut."""

    def test_uses_ffmpeg_antigate_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Anti-gate açık + ffmpeg varsa TTS de anti-gate filtresinden geçer."""
        monkeypatch.setattr(audio_module.shutil, "which", _which_factory({"ffmpeg", "mpg123"}))

        cmd = build_tts_command(AntiGateConfig(enabled=True))

        assert cmd is not None
        assert cmd[0] == "ffmpeg"
        assert "-filter_complex" in cmd
        assert "pipe:0" in cmd

    def test_falls_back_to_mpg123_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Anti-gate kapalıyken TTS mpg123 ile stdin'den çalar."""
        monkeypatch.setattr(audio_module.shutil, "which", _which_factory({"ffmpeg", "mpg123"}))

        cmd = build_tts_command(AntiGateConfig(enabled=False))

        assert cmd == ["mpg123", "-q", "-"]

    def test_none_when_no_player_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ne ffmpeg ne mpg123 varken komut üretilemez (None)."""
        monkeypatch.setattr(audio_module.shutil, "which", _which_factory(set()))

        assert build_tts_command(AntiGateConfig(enabled=True)) is None
