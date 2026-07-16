"""APScheduler based scheduler implementation."""

import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED, JobEvent
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from vakit_pi.services.ports import SchedulerPort

logger = logging.getLogger(__name__)


class APSchedulerAdapter(SchedulerPort):
    """APScheduler ile zamanlama adaptörü."""

    def __init__(self) -> None:
        """Initialize scheduler."""
        jobstores = {"default": MemoryJobStore()}
        self._scheduler = AsyncIOScheduler(jobstores=jobstores)
        self._started = False

        # Event listener'ları ekle
        self._scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        self._scheduler.add_listener(self._job_missed_listener, EVENT_JOB_MISSED)

    def _job_executed_listener(self, event: JobEvent) -> None:
        """İş başarıyla çalıştığında log yaz."""
        logger.info(f"İş başarıyla çalıştı: {event.job_id}")

    def _job_error_listener(self, event: JobEvent) -> None:
        """İş çalışırken hata olduğunda log yaz."""
        logger.error(
            f"İş çalışırken hata oluştu: {event.job_id}, Hata: {event.exception}",
            exc_info=event.exception,
        )

    def _job_missed_listener(self, event: JobEvent) -> None:
        """İş kaçırıldığında log yaz."""
        logger.warning(f"İş kaçırıldı (misfire): {event.job_id}")

    def start(self) -> None:
        """Scheduler'ı başlat."""
        if not self._started:
            self._scheduler.start()
            self._started = True
            logger.info("APScheduler başlatıldı.")

    def shutdown(self) -> None:
        """Scheduler'ı kapat."""
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("APScheduler kapatıldı.")

    def schedule_at(
        self,
        run_time: datetime,
        callback: Callable[[], None] | Callable[[], Coroutine[Any, Any, None]],
        job_id: str,
    ) -> None:
        """Belirtilen zamanda çalıştırılacak iş planla."""
        if not self._started:
            self.start()

        # Varsa eski işi sil
        existing = self._scheduler.get_job(job_id)
        if existing:
            self._scheduler.remove_job(job_id)

        trigger = DateTrigger(run_date=run_time)
        self._scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=60,  # 1 dakika tolerans
        )
        logger.debug(f"İş planlandı: {job_id} -> {run_time}")

    def cancel(self, job_id: str) -> bool:
        """Planlanmış işi iptal et."""
        try:
            self._scheduler.remove_job(job_id)
            logger.debug(f"İş iptal edildi: {job_id}")
            return True
        except Exception:
            return False

    def cancel_all(self) -> None:
        """Tüm işleri iptal et."""
        self._scheduler.remove_all_jobs()
        logger.info("Tüm planlanmış işler iptal edildi.")

    def get_scheduled_jobs(self) -> list[tuple[str, datetime]]:
        """Planlanmış işleri listele."""
        jobs = self._scheduler.get_jobs()
        result = []
        for job in jobs:
            if job.next_run_time:
                result.append((job.id, job.next_run_time))
        return sorted(result, key=lambda x: x[1])
