"""Prayer time calculation service."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pyIslam.praytimes import Prayer, PrayerConf
from timezonefinder import TimezoneFinder

from vakit_pi.domain.models import (
    DIYANET_OFFSETS,
    Location,
    PrayerName,
    PrayerOffsets,
    PrayerTime,
    PrayerTimes,
)
from vakit_pi.services.ports import PrayerTimeCalculatorPort

# Türkiye timezone'ları
TURKEY_TIMEZONES = {"Europe/Istanbul", "Asia/Istanbul"}


class PrayerService(PrayerTimeCalculatorPort):
    """Namaz vakti hesaplama servisi."""

    def __init__(
        self,
        location: Location,
        *,
        fajr_isha_method: int = 2,
        asr_fiqh: int = 1,
        offsets: PrayerOffsets | None = None,
        rounding_seconds: int = 30,
        auto_diyanet_offsets: bool = True,
    ) -> None:
        """
        Initialize prayer service.

        Args:
            location: Konum bilgisi
            fajr_isha_method: İmsak/yatsı hesaplama metodu (2=Diyanet)
            asr_fiqh: Fıkhi mezhep (1=Hanefi, 0=Şafi)
            offsets: Temkin süreleri
            rounding_seconds: Yuvarlama saniyesi
            auto_diyanet_offsets: Türkiye'de otomatik Diyanet offsetleri
        """
        self._location = location
        self._fajr_isha_method = fajr_isha_method
        self._asr_fiqh = asr_fiqh
        self._rounding_seconds = rounding_seconds

        # Timezone hesapla
        tzf = TimezoneFinder()
        self._tz_name = tzf.timezone_at(lat=location.latitude, lng=location.longitude)
        if self._tz_name is None:
            self._tz_name = "UTC"
        self._tz = ZoneInfo(self._tz_name)

        # Offset belirleme
        if offsets is not None:
            self._offsets = offsets
        elif auto_diyanet_offsets and self.is_in_turkey:
            self._offsets = DIYANET_OFFSETS
        else:
            self._offsets = PrayerOffsets()

    @property
    def is_in_turkey(self) -> bool:
        """Koordinatlar Türkiye'de mi?"""
        return self._tz_name in TURKEY_TIMEZONES

    @property
    def timezone(self) -> ZoneInfo:
        """Timezone nesnesi."""
        return self._tz

    @property
    def timezone_name(self) -> str:
        """Timezone adı."""
        return self._tz_name

    @property
    def timezone_offset(self) -> int:
        """UTC offset saat cinsinden."""
        now = datetime.now(self._tz)
        offset = now.utcoffset()
        if offset is None:
            return 0
        return int(offset.total_seconds() / 3600)

    @property
    def location(self) -> Location:
        """Konum bilgisi."""
        return self._location

    @property
    def offsets(self) -> PrayerOffsets:
        """Temkin süreleri."""
        return self._offsets

    def update_location(self, location: Location) -> None:
        """Konum güncelle ve timezone'u yeniden hesapla."""
        self._location = location
        tzf = TimezoneFinder()
        self._tz_name = tzf.timezone_at(lat=location.latitude, lng=location.longitude) or "UTC"
        self._tz = ZoneInfo(self._tz_name)

    def update_offsets(self, offsets: PrayerOffsets) -> None:
        """Temkin sürelerini güncelle."""
        self._offsets = offsets

    def _apply_offset(self, time_obj: time, target_date: date, minutes: int) -> time:
        """Vakite offset uygula ve time nesnesi döndür."""
        dt = datetime.combine(target_date, time_obj)
        adjusted = dt + timedelta(minutes=minutes, seconds=self._rounding_seconds)
        return adjusted.time().replace(second=0, microsecond=0)

    def calculate(self, target_date: date) -> PrayerTimes:
        """Belirtilen tarih için namaz vakitlerini hesapla."""
        conf = PrayerConf(
            self._location.longitude,
            self._location.latitude,
            self.timezone_offset,
            self._fajr_isha_method,
            self._asr_fiqh,
        )
        prayer = Prayer(conf, target_date)

        return PrayerTimes(
            date=target_date,
            fajr=self._apply_offset(prayer.fajr_time(), target_date, self._offsets.fajr),
            sunrise=self._apply_offset(prayer.sherook_time(), target_date, self._offsets.sunrise),
            dhuhr=self._apply_offset(prayer.dohr_time(), target_date, self._offsets.dhuhr),
            asr=self._apply_offset(prayer.asr_time(), target_date, self._offsets.asr),
            maghrib=self._apply_offset(prayer.maghreb_time(), target_date, self._offsets.maghrib),
            isha=self._apply_offset(prayer.ishaa_time(), target_date, self._offsets.isha),
        )

    def calculate_range(self, start_date: date, days: int) -> list[PrayerTimes]:
        """Belirtilen tarihten itibaren n gün için vakitleri hesapla."""
        return [self.calculate(start_date + timedelta(days=i)) for i in range(days)]

    def get_current_prayer(self, now: datetime | None = None) -> PrayerName:
        """Şu anki namaz vaktini döndür."""
        if now is None:
            now = datetime.now(self._tz)

        today_times = self.calculate(now.date())
        current_time = now.time()

        # Sırayla kontrol et (sondan başa)
        prayers_order = [
            (PrayerName.ISHA, today_times.isha),
            (PrayerName.MAGHRIB, today_times.maghrib),
            (PrayerName.ASR, today_times.asr),
            (PrayerName.DHUHR, today_times.dhuhr),
            (PrayerName.SUNRISE, today_times.sunrise),
            (PrayerName.FAJR, today_times.fajr),
        ]

        for prayer, prayer_time in prayers_order:
            if current_time >= prayer_time:
                return prayer

        # Gece yarısından sonra, yatsı vakti
        return PrayerName.ISHA

    def get_next_prayer(self, now: datetime | None = None) -> PrayerTime:
        """Sonraki namaz vaktini döndür."""
        if now is None:
            now = datetime.now(self._tz)

        today_times = self.calculate(now.date())
        current_time = now.time()

        # Bugünkü vakitleri kontrol et
        for prayer in PrayerName:
            prayer_time = today_times.get_time(prayer)
            if current_time < prayer_time:
                return PrayerTime(name=prayer, time=prayer_time, date=now.date())

        # Yarının ilk vakti (imsak)
        tomorrow = now.date() + timedelta(days=1)
        tomorrow_times = self.calculate(tomorrow)
        return PrayerTime(
            name=PrayerName.FAJR,
            time=tomorrow_times.fajr,
            date=tomorrow,
        )

    def get_time_until_next_prayer(self, now: datetime | None = None) -> timedelta:
        """Sonraki namaz vaktine kalan süre."""
        if now is None:
            now = datetime.now(self._tz)

        next_prayer = self.get_next_prayer(now)
        next_datetime = datetime.combine(next_prayer.date, next_prayer.time)
        next_datetime = next_datetime.replace(tzinfo=self._tz)

        return next_datetime - now
