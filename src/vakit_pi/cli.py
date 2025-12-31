"""Command-line interface for Vakit-Pi."""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from vakit_pi import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="vakit-pi",
        description="Raspberry Pi için Namaz Vakti ve Ezan Uygulaması",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"vakit-pi {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Komutlar")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Web sunucusunu başlat")
    serve_parser.add_argument(
        "--host",
        "-H",
        default="0.0.0.0",
        help="Sunucu adresi (varsayılan: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="Sunucu portu (varsayılan: 8080)",
    )
    serve_parser.add_argument(
        "--settings",
        "-s",
        type=Path,
        help="Ayar dosyası yolu",
    )
    serve_parser.add_argument(
        "--audio-dir",
        "-a",
        type=Path,
        help="Ezan ses dosyaları dizini",
    )
    serve_parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log seviyesi (varsayılan: INFO)",
    )

    # times command
    times_parser = subparsers.add_parser("times", help="Namaz vakitlerini göster")
    times_parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Enlem",
    )
    times_parser.add_argument(
        "--lng",
        type=float,
        required=True,
        help="Boylam",
    )
    times_parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=1,
        help="Kaç günlük (varsayılan: 1)",
    )

    # test-audio command
    test_parser = subparsers.add_parser("test-audio", help="Ses testi yap")
    test_parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Test edilecek ses dosyası",
    )
    test_parser.add_argument(
        "--volume",
        "-V",
        type=int,
        default=80,
        help="Ses seviyesi (0-100, varsayılan: 80)",
    )

    return parser


def cmd_serve(args: argparse.Namespace) -> None:
    """Run the web server."""
    import uvicorn

    from vakit_pi.api.app import create_app
    from vakit_pi.config import setup_logging

    setup_logging(args.log_level)

    app = create_app(
        settings_path=args.settings,
        audio_dir=args.audio_dir,
    )

    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


def cmd_times(args: argparse.Namespace) -> None:
    """Show prayer times."""
    from vakit_pi.domain.models import Location
    from vakit_pi.services.prayer_service import PrayerService

    location = Location(latitude=args.lat, longitude=args.lng)
    service = PrayerService(location)

    now = datetime.now(service.timezone)
    times_list = service.calculate_range(now.date(), args.days)

    print(f"\n📍 Konum: {args.lat:.4f}, {args.lng:.4f}")
    print(f"🌍 Timezone: {service.timezone_name}")
    print(f"🇹🇷 Türkiye'de: {'Evet' if service.is_in_turkey else 'Hayır'}")
    print()

    print("=" * 75)
    print(
        f"{'Tarih':<15} {'İmsak':>8} {'Güneş':>8} {'Öğle':>8} {'İkindi':>8} {'Akşam':>8} {'Yatsı':>8}"
    )
    print("-" * 75)

    for times in times_list:
        print(
            f"{times.date.strftime('%d.%m.%Y'):<15} "
            f"{times.fajr.strftime('%H:%M'):>8} "
            f"{times.sunrise.strftime('%H:%M'):>8} "
            f"{times.dhuhr.strftime('%H:%M'):>8} "
            f"{times.asr.strftime('%H:%M'):>8} "
            f"{times.maghrib.strftime('%H:%M'):>8} "
            f"{times.isha.strftime('%H:%M'):>8}"
        )

    print("=" * 75)


def cmd_test_audio(args: argparse.Namespace) -> None:
    """Test audio playback."""
    from vakit_pi.infrastructure.audio import get_best_player

    async def _test():
        player = get_best_player()
        print(f"🔊 Ses oynatıcı: {player.__class__.__name__}")

        # Varsayılan ezan dosyası
        file_path = args.file or Path(__file__).parent / "assets" / "audio" / "adhan_istanbul.mp3"

        if not file_path.exists():
            print(f"❌ Dosya bulunamadı: {file_path}")
            return

        print(f"📂 Dosya: {file_path}")
        print(f"🔈 Ses seviyesi: {args.volume}%")
        print("▶️  Çalınıyor...")

        try:
            await player.play(str(file_path), volume=args.volume)
            print("✅ Tamamlandı!")
        except Exception as e:
            print(f"❌ Hata: {e}")

    asyncio.run(_test())


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        # Varsayılan olarak serve çalıştır
        args.command = "serve"
        args.host = "0.0.0.0"
        args.port = 8080
        args.settings = None
        args.audio_dir = None
        args.log_level = "INFO"

    commands = {
        "serve": cmd_serve,
        "times": cmd_times,
        "test-audio": cmd_test_audio,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
