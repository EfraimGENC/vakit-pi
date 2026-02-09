# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vakit-Pi is a Python application for Raspberry Pi that calculates Islamic prayer times and plays Adhan (call to prayer) through Bluetooth speakers. Built with FastAPI + Uvicorn, it uses Hexagonal Architecture (Ports & Adapters) with Clean Architecture principles.

**Target Platform**: Raspberry Pi 4 / Raspberry Pi OS Debian Bookworm 64-bit

## Common Commands

```bash
# Development
just serve              # Run dev server (http://localhost:8080)
just check              # Full quality checks: lint, format, typecheck, test
just test               # Run tests
just lint               # Ruff linter
just format             # Code formatting
just typecheck          # MyPy type checking

# Individual uv commands
uv sync                 # Install dependencies
uv sync --all-extras    # Install with dev dependencies
uv run pytest           # Run tests directly
uv run pytest tests/test_api.py  # Run specific test file

# CLI
uv run vakit-pi serve   # Run web server
uv run vakit-pi times --lat 41.0082 --lng 28.9784 --days 7  # Show prayer times
uv run vakit-pi test-audio --volume 80  # Audio test

# Deployment (on Raspberry Pi)
just update             # git pull + uv sync + restart service
just status             # Show service status
just logs               # Follow service logs
just restart            # Restart systemd service
```

## Architecture

```
src/vakit_pi/
├── domain/           # Core business logic (DDD)
│   ├── models.py     # Value objects: PrayerName, Location, PrayerSettings, PrayerTimes
│   └── events.py     # Domain events: PrayerTimeReachedEvent, AdhanStartedEvent, etc.
├── services/         # Business logic layer
│   ├── ports.py      # Port interfaces (AudioPlayerPort, SchedulerPort, etc.)
│   ├── prayer_service.py    # Prayer time calculation (uses pyIslam)
│   ├── adhan_service.py     # Adhan playback orchestration
│   └── scheduler_service.py # APScheduler-based job scheduling
├── infrastructure/   # Adapters (external system implementations)
│   ├── audio.py      # Multiple players: Mpg123, Aplay, Ffplay, PulseAudio
│   ├── scheduler.py  # APScheduler adapter
│   ├── settings_repository.py  # JSON settings persistence
│   └── event_bus.py  # In-memory event bus
├── api/              # FastAPI REST layer
│   ├── app.py        # FastAPI app factory with lifespan
│   ├── routes.py     # API endpoints
│   ├── schemas.py    # Pydantic validation schemas
│   └── dependencies.py  # AppState and dependency injection
├── assets/audio/     # Adhan MP3 files
└── web/              # Frontend static files
```

**Key Patterns**:
- **Ports & Adapters**: Interfaces in `services/ports.py`, implementations in `infrastructure/`
- **Event-Driven**: Services communicate via `InMemoryEventBus` domain events
- **Dependency Injection**: `AppState` dataclass holds all services, injected via FastAPI `Depends()`
- **Frozen Dataclasses**: Domain models use `frozen=True` for immutability

## Code Style

- **Python**: 3.12+
- **Linter/Formatter**: Ruff (line length: 100, double quotes)
- **Type Checker**: MyPy strict mode - all functions must have type hints
- **Package Manager**: `uv` (Astral)

Turkish Unicode characters are allowed (RUF001/002/003 ignored). Turkish commit messages are accepted.

## Settings

Persisted to `~/.config/vakit-pi/settings.json`. Key environment variables:
- `VAKIT_PI_HOST` (default: `0.0.0.0`)
- `VAKIT_PI_PORT` (default: `8080`)
- `VAKIT_PI_LOG_LEVEL` (default: `INFO`)
- `VAKIT_PI_SETTINGS_PATH`

## Deployment Target

- SSH: `ssh efraim@192.168.1.22`
- Project directory: `~/vakit-pi`
- Service: `vakit-pi.service` (systemd)
