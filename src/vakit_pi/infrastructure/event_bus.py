"""In-memory event bus implementation."""

import logging
from collections import defaultdict
from collections.abc import Callable

from vakit_pi.domain.events import DomainEvent
from vakit_pi.services.ports import EventBusPort

logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBusPort):
    """Basit in-memory event bus."""

    def __init__(self) -> None:
        """Initialize event bus."""
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = defaultdict(
            list
        )

    def publish(self, event: DomainEvent) -> None:
        """Event yayınla."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        logger.debug(f"Event yayınlandı: {event_type.__name__} ({len(handlers)} handler)")

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler hatası: {e}")

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], None],
    ) -> None:
        """Event tipine abone ol."""
        self._handlers[event_type].append(handler)
        logger.debug(f"Event aboneliği: {event_type.__name__}")

    def unsubscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], None],
    ) -> None:
        """Event aboneliğini iptal et."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Event aboneliği iptal: {event_type.__name__}")

    def clear_all(self) -> None:
        """Tüm abonelikleri temizle."""
        self._handlers.clear()
