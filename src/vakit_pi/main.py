"""Main entry point for Vakit-Pi application."""

import logging

import uvicorn

from vakit_pi.api.app import create_app
from vakit_pi.config import get_config, setup_logging


def main() -> None:
    """Run the Vakit-Pi application."""
    config = get_config()
    setup_logging(config.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Vakit-Pi başlatılıyor...")
    logger.info(f"Ayar dosyası: {config.settings_path}")
    logger.info(f"Audio dizini: {config.audio_dir}")

    app = create_app(
        settings_path=config.settings_path,
        audio_dir=config.audio_dir,
        static_dir=config.static_dir,
    )

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
