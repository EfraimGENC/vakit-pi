"""APScheduler based scheduler implementation."""

import logging
from collections.abc import Callable
from datetime import datetime

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
        callback: Callable[[], None],
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
