"""Domain events for event-driven architecture."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from vakit_pi.domain.models import PrayerName, PrayerTime


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for domain events."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, kw_only=True)
class PrayerTimeReachedEvent(DomainEvent):
    """Namaz vakti geldiğinde tetiklenen event."""

    prayer_time: PrayerTime
    should_play_adhan: bool = True


@dataclass(frozen=True, kw_only=True)
class PreAlertEvent(DomainEvent):
    """Namaz vaktinden önce uyarı eventi."""

    prayer_time: PrayerTime
    minutes_before: int


@dataclass(frozen=True, kw_only=True)
class AdhanStartedEvent(DomainEvent):
    """Ezan çalmaya başladığında."""

    prayer: PrayerName
    volume: int


@dataclass(frozen=True, kw_only=True)
class AdhanFinishedEvent(DomainEvent):
    """Ezan bittiğinde."""

    prayer: PrayerName


@dataclass(frozen=True, kw_only=True)
class SettingsChangedEvent(DomainEvent):
    """Ayarlar değiştiğinde."""

    changed_fields: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class AudioErrorEvent(DomainEvent):
    """Ses çalma hatası."""

    error_message: str
    prayer: PrayerName | None = None
