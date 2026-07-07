"""Audio player implementations for Raspberry Pi."""

import asyncio
import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from vakit_pi.services.ports import AudioPlayerPort

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    """Ortam değişkenini boolean olarak oku."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class AntiGateConfig:
    """Behringer noise gate'ini oynatım sırasında açık tutan işleme ayarları.

    Parametreler ortam değişkenleriyle ayarlanır; Behringer'ın eşiği bilinmediğinden
    Pi'de deneyerek ince ayar yapılır.
    """

    enabled: bool = True
    leadin_seconds: float = 1.5
    tone_hz: int = 55
    compress: bool = True
    floor_db: float | None = None
    # Çıkışa eklenen dolgu sessizlik (saniye). ffmpeg pulse çıkışı buffer'ı drain
    # etmeden sonlandığı için son ~1.5s kesiliyor; bu dolgu içeriğin tamamının
    # çalınmasını garanti eder. PulseAudio latency'sinden büyük olmalı.
    tail_seconds: float = 2.5

    @classmethod
    def from_env(cls) -> "AntiGateConfig":
        """Ortam değişkenlerinden yapılandırma yükle."""
        floor_raw = os.getenv("VAKIT_PI_ANTIGATE_FLOOR_DB", "off").strip().lower()
        floor_db = None if floor_raw in ("", "off", "none") else float(floor_raw)

        return cls(
            enabled=_env_bool("VAKIT_PI_ANTIGATE", True),
            leadin_seconds=float(os.getenv("VAKIT_PI_ANTIGATE_LEADIN", "1.5")),
            tone_hz=int(os.getenv("VAKIT_PI_ANTIGATE_TONE_HZ", "55")),
            compress=_env_bool("VAKIT_PI_ANTIGATE_COMPRESS", True),
            floor_db=floor_db,
            tail_seconds=float(os.getenv("VAKIT_PI_ANTIGATE_TAIL", "2.5")),
        )


# Lead-in ısıtma tonunun tepe seviyesi (lineer). Gate'i açacak kadar var,
# ezandan önce rahatsız etmeyecek kadar kısık.
_LEADIN_GAIN = 0.2
# concat/amix'in aynı formatta stream beklemesi için ortak ses formatı.
_AUDIO_FORMAT = "aformat=sample_fmts=fltp:channel_layouts=stereo"


def build_antigate_filter(config: AntiGateConfig, volume: int) -> str:
    """ffmpeg filter_complex zincirini kur.

    Zincir dört bileşenden oluşur; hiçbiri toplam süre bilgisi gerektirmez, böylece
    hem statik dosya hem canlı TTS stream'i için aynı filtre kullanılabilir:

    1. Lead-in ısıtma tonu (asıl sesin önüne concat) → gate/Bluetooth linki ilk
       hece gelmeden açılır.
    2. Dinamik normalizasyon (dynaudnorm) → yumuşak kısımlar yükselir, ortadaki
       kelime başları gate eşiğinin üstünde kalır.
    3. Opsiyonel taban tonu (amix) → nefes anlarında gate tam kapanmaz.
    4. Tail dolgu (apad) → ffmpeg pulse çıkışı buffer'ı drain etmeden sonlandığı
       için son ~1.5s kesiliyordu; dolgu sessizlik içeriğin tamamını korur.

    Çıkış etiketi her zaman ``[out]``.
    """
    gain = max(0.0, min(volume, 100)) / 100

    main = f"[0:a]aresample=48000,{_AUDIO_FORMAT}"
    if config.compress:
        main += ",dynaudnorm"
    main += f",volume={gain:g}[main]"

    parts: list[str] = []

    # 1. Lead-in ısıtma tonu + ana ses → [body]
    if config.leadin_seconds > 0:
        parts.append(
            f"sine=frequency={config.tone_hz}:duration={config.leadin_seconds:g}"
            f":sample_rate=48000,{_AUDIO_FORMAT},volume={_LEADIN_GAIN:g},"
            f"afade=t=in:d=0.25[lead]"
        )
        parts.append(main)
        parts.append("[lead][main]concat=n=2:v=0:a=1[body]")
        body = "[body]"
    else:
        parts.append(main)
        body = "[main]"

    # 2. Opsiyonel taban tonu → [mixed]
    if config.floor_db is not None:
        parts.append(
            f"sine=frequency={config.tone_hz}:sample_rate=48000,"
            f"{_AUDIO_FORMAT},volume={config.floor_db:g}dB[floor]"
        )
        parts.append(f"{body}[floor]amix=inputs=2:duration=first:normalize=0[mixed]")
        mixed = "[mixed]"
    else:
        mixed = body

    # 3. Tail dolgu (drain telafisi) → [out]
    if config.tail_seconds > 0:
        parts.append(f"{mixed}apad=pad_dur={config.tail_seconds:g}[out]")
    else:
        parts.append(f"{mixed}anull[out]")

    return ";".join(parts)


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
            logger.warning(f"Player çıkış kodu: {self._process.returncode}, hata: {error_msg}")

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


class FfmpegAntiGatePlayer(BaseAudioPlayer):
    """ffmpeg ile anti-gate işleme uygulayarak PulseAudio'ya (Bluetooth) çalar.

    Lead-in ısıtma tonu + dinamik normalizasyon + opsiyonel taban tonu ile Behringer
    noise gate'ini oynatım süresince açık tutar. Oynatım bitince tam sessizliğe döner.
    """

    def __init__(self, config: AntiGateConfig | None = None) -> None:
        super().__init__()
        self._config = config or AntiGateConfig.from_env()

    def _is_available(self) -> bool:
        """ffmpeg kurulu mu?"""
        return shutil.which("ffmpeg") is not None

    def _get_command(self, file_path: str, volume: int) -> list[str]:
        """ffmpeg komutu oluştur.

        file_path '-' ise ffmpeg stdin'den (pipe:0) okur — TTS stream'i için.
        """
        chain = build_antigate_filter(self._config, volume)
        input_arg = "pipe:0" if file_path == "-" else file_path

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
        if input_arg != "pipe:0":
            # Dosya oynatımında ffmpeg'in klavye stdin'ini yutmasını engelle.
            cmd.append("-nostdin")
        cmd += [
            "-i",
            input_arg,
            "-filter_complex",
            chain,
            "-map",
            "[out]",
            "-f",
            "pulse",
            "default",
        ]
        return cmd


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
            "-o",
            "pulse",  # PulseAudio çıkışı (Bluetooth için gerekli)
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


def get_best_player(antigate: AntiGateConfig | None = None) -> BaseAudioPlayer:
    """Sistemde mevcut en iyi player'ı döndür.

    ffmpeg mevcut ve anti-gate açıksa Behringer noise gate'ini aşan
    FfmpegAntiGatePlayer tercih edilir; aksi halde mevcut oynatıcı zincirine düşülür.
    """
    antigate = antigate or AntiGateConfig.from_env()

    if antigate.enabled and shutil.which("ffmpeg") is not None:
        logger.info("Ses oynatıcı seçildi: ffmpeg (anti-gate)")
        return FfmpegAntiGatePlayer(antigate)

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


def build_tts_command(antigate: AntiGateConfig | None = None) -> list[str] | None:
    """TTS stream'ini (mp3, stdin'den) oynatacak komutu döndür.

    Anti-gate açık ve ffmpeg mevcutsa TTS de anti-gate filtresinden geçer; aksi
    halde mpg123'e düşülür. Hiçbiri yoksa None.
    """
    antigate = antigate or AntiGateConfig.from_env()

    if antigate.enabled and shutil.which("ffmpeg") is not None:
        return FfmpegAntiGatePlayer(antigate)._get_command("-", volume=100)

    if shutil.which("mpg123") is not None:
        return ["mpg123", "-q", "-"]

    return None


async def speak_tts(
    text: str,
    voice: str = "tr-TR-AhmetNeural",
    antigate: AntiGateConfig | None = None,
) -> None:
    """
    edge-tts kullanarak metni sesli oku.

    Args:
        text: Okunacak metin
        voice: Kullanılacak ses (varsayılan: tr-TR-AhmetNeural)
        antigate: Anti-gate yapılandırması (None ise ortamdan yüklenir)
    """
    cmd = build_tts_command(antigate)
    if cmd is None:
        logger.warning("TTS için ffmpeg veya mpg123 gerekli")
        return

    try:
        import edge_tts
    except ImportError:
        logger.warning("TTS için edge-tts paketi gerekli: uv add edge-tts")
        return

    logger.info(f"TTS çalıştırılıyor: {text}")

    try:
        communicate = edge_tts.Communicate(text, voice)

        # edge-tts'den gelen audio'yu oynatıcıya pipe et (anti-gate ffmpeg veya mpg123)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and process.stdin:
                process.stdin.write(chunk["data"])
                await process.stdin.drain()

        if process.stdin:
            process.stdin.close()
            await process.stdin.wait_closed()

        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else ""
            logger.warning(f"TTS hatası: {error_msg}")
        else:
            logger.info("TTS tamamlandı")

    except Exception as e:
        logger.error(f"TTS çalıştırma hatası: {e}")
