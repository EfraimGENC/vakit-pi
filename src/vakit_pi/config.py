"""Configuration management."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self


def _get_default_settings_path() -> Path:
    """Get default settings path."""
    return Path.home() / ".config" / "vakit-pi" / "settings.json"


def _get_default_audio_dir() -> Path:
    """Get default audio directory."""
    return Path(__file__).parent / "assets" / "audio"


def _get_default_static_dir() -> Path:
    """Get default static files directory."""
    return Path(__file__).parent / "web"


@dataclass
class AppConfig:
    """Application configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"

    # File paths
    settings_path: Path = field(default_factory=_get_default_settings_path)
    audio_dir: Path = field(default_factory=_get_default_audio_dir)
    static_dir: Path = field(default_factory=_get_default_static_dir)

    @classmethod
    def from_env(cls) -> Self:
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("VAKIT_PI_HOST", "0.0.0.0"),
            port=int(os.getenv("VAKIT_PI_PORT", "8080")),
            log_level=os.getenv("VAKIT_PI_LOG_LEVEL", "INFO"),
            settings_path=Path(
                os.getenv("VAKIT_PI_SETTINGS_PATH", str(_get_default_settings_path()))
            ),
            audio_dir=Path(os.getenv("VAKIT_PI_AUDIO_DIR", str(_get_default_audio_dir()))),
            static_dir=Path(os.getenv("VAKIT_PI_STATIC_DIR", str(_get_default_static_dir()))),
        )


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get application configuration."""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config


def setup_logging(level: str = "INFO") -> None:
    """Setup application logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
