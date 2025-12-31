"""Scheduler service for prayer time scheduling."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from vakit_pi.domain.events import PrayerTimeReachedEvent, PreAlertEvent
from vakit_pi.domain.models import PrayerName, PrayerSettings, PrayerTime
from vakit_pi.services.adhan_service import AdhanService
from vakit_pi.services.ports import EventBusPort, SchedulerPort
from vakit_pi.services.prayer_service import PrayerService

logger = logging.getLogger(__name__)


class SchedulerService:
    """Namaz vakitleri için zamanlama servisi."""

    def __init__(
        self,
        prayer_service: PrayerService,
        adhan_service: AdhanService,
        scheduler: SchedulerPort,
        event_bus: EventBusPort | None = None,
    ) -> None:
        """
        Initialize scheduler service.

        Args:
            prayer_service: Namaz vakti hesaplama servisi
            adhan_service: Ezan çalma servisi
            scheduler: Zamanlayıcı adaptörü
            event_bus: Event bus (opsiyonel)
        """
        self._prayer_service = prayer_service
        self._adhan_service = adhan_service
        self._scheduler = scheduler
        self._event_bus = event_bus
        self._running = False
        self._scheduled_count = 0

    @property
    def settings(self) -> PrayerSettings:
        """Mevcut ayarlar."""
        return self._adhan_service.settings

    def _make_job_id(self, prayer: PrayerName, date: datetime, suffix: str = "") -> str:
        """İş için benzersiz ID oluştur."""
        base_id = f"prayer_{prayer.value}_{date.strftime('%Y%m%d')}"
        return f"{base_id}_{suffix}" if suffix else base_id

    def _create_adhan_callback(self, prayer_time: PrayerTime) -> Callable[[], None]:
        """Ezan çalma callback'i oluştur."""

        def callback() -> None:
            logger.info(f"Ezan vakti geldi: {prayer_time.name.display_name}")

            if self._event_bus:
                self._event_bus.publish(
                    PrayerTimeReachedEvent(
                        prayer_time=prayer_time,
                        should_play_adhan=self.settings.is_prayer_enabled(prayer_time.name),
                    )
                )

            # Async fonksiyonu sync context'te çalıştır
            # Task referansını saklamak gerekmiyor çünkü fire-and-forget pattern
            asyncio.create_task(self._adhan_service.play_adhan(prayer_time.name))  # noqa: RUF006

        return callback

    def _create_pre_alert_callback(
        self, prayer_time: PrayerTime, minutes_before: int
    ) -> Callable[[], None]:
        """Ön uyarı callback'i oluştur."""

        def callback() -> None:
            logger.info(f"{prayer_time.name.display_name} vaktine {minutes_before} dakika kaldı")

            if self._event_bus:
                self._event_bus.publish(
                    PreAlertEvent(
                        prayer_time=prayer_time,
                        minutes_before=minutes_before,
                    )
                )

        return callback

    def schedule_day(self, target_date: datetime | None = None) -> int:
        """
        Bir günün namaz vakitlerini planla.

        Args:
            target_date: Hedef tarih (varsayılan: bugün)

        Returns:
            Planlanan iş sayısı
        """
        if target_date is None:
            target_date = datetime.now(self._prayer_service.timezone)

        prayer_times = self._prayer_service.calculate(target_date.date())
        now = datetime.now(self._prayer_service.timezone)
        scheduled = 0
        pre_alert_minutes = self.settings.pre_alert_minutes

        for prayer in PrayerName:
            prayer_time = prayer_times.get_prayer_time(prayer)
            prayer_datetime = datetime.combine(
                prayer_time.date,
                prayer_time.time,
                tzinfo=self._prayer_service.timezone,
            )

            # Geçmiş vakitleri atla
            if prayer_datetime <= now:
                continue

            # Sadece aktif vakitleri planla
            if not self.settings.is_prayer_enabled(prayer):
                continue

            # Ana ezan zamanlaması
            job_id = self._make_job_id(prayer, prayer_datetime)
            self._scheduler.schedule_at(
                run_time=prayer_datetime,
                callback=self._create_adhan_callback(prayer_time),
                job_id=job_id,
            )
            scheduled += 1
            logger.debug(f"Planlandı: {prayer.display_name} -> {prayer_datetime}")

            # Ön uyarı zamanlaması
            if pre_alert_minutes > 0:
                pre_alert_time = prayer_datetime - timedelta(minutes=pre_alert_minutes)
                if pre_alert_time > now:
                    pre_alert_job_id = self._make_job_id(prayer, prayer_datetime, "pre")
                    self._scheduler.schedule_at(
                        run_time=pre_alert_time,
                        callback=self._create_pre_alert_callback(prayer_time, pre_alert_minutes),
                        job_id=pre_alert_job_id,
                    )
                    scheduled += 1

        self._scheduled_count = scheduled
        logger.info(f"{target_date.date()} için {scheduled} iş planlandı.")
        return scheduled

    def reschedule(self) -> int:
        """Tüm planlamaları yeniden yap."""
        self._scheduler.cancel_all()
        return self.schedule_day()

    def get_scheduled_jobs(self) -> list[tuple[str, datetime]]:
        """Planlanmış işleri listele."""
        return self._scheduler.get_scheduled_jobs()

    async def start(self) -> None:
        """Zamanlayıcıyı başlat."""
        if self._running:
            logger.warning("Scheduler zaten çalışıyor.")
            return

        self._running = True
        logger.info("Scheduler başlatıldı.")

        # Bugünün vakitlerini planla
        self.schedule_day()

        # Her gece yarısı ertesi günü planla
        while self._running:
            now = datetime.now(self._prayer_service.timezone)
            tomorrow = now.date() + timedelta(days=1)
            next_midnight = datetime.combine(
                tomorrow,
                datetime.min.time(),
                tzinfo=self._prayer_service.timezone,
            )

            # Gece yarısına kadar bekle
            wait_seconds = (next_midnight - now).total_seconds()
            logger.debug(f"Gece yarısına {wait_seconds:.0f} saniye kaldı.")

            try:
                await asyncio.sleep(wait_seconds + 60)  # +1 dakika güvenlik marjı
                if self._running:
                    self.schedule_day()
            except asyncio.CancelledError:
                break

    async def stop(self) -> None:
        """Zamanlayıcıyı durdur."""
        self._running = False
        self._scheduler.cancel_all()
        logger.info("Scheduler durduruldu.")
