from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from babel.dates import format_date
from pyIslam.praytimes import Prayer, PrayerConf
from timezonefinder import TimezoneFinder


@dataclass
class PrayerOffsets:
    """Namaz vakitlerine uygulanacak offset değerleri (dakika)"""

    fajr: int = 0
    sunrise: int = 0
    dhuhr: int = 0
    asr: int = 0
    maghrib: int = 0
    isha: int = 0


# Diyanet'in kullandığı temkin süreleri
DIYANET_OFFSETS = PrayerOffsets(fajr=0, sunrise=-7, dhuhr=5, asr=4, maghrib=7, isha=0)

# Türkiye timezone'ları
TURKEY_TIMEZONES = {"Europe/Istanbul", "Asia/Istanbul"}


@dataclass
class PrayerTimes:
    """Hesaplanmış namaz vakitleri"""

    imsak: str
    gunes: str
    ogle: str
    ikindi: str
    aksam: str
    yatsi: str


class PrayerTimeCalculator:
    """Namaz vakti hesaplayıcı"""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        *,
        fajr_isha_method: int = 2,
        asr_fiqh: int = 1,
        offsets: Optional[PrayerOffsets] = None,
        rounding_seconds: int = 30,
        auto_diyanet_offsets: bool = True,
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.fajr_isha_method = fajr_isha_method
        self.asr_fiqh = asr_fiqh
        self.rounding_seconds = rounding_seconds

        self._tzf = TimezoneFinder()
        self._tz_name = self._tzf.timezone_at(lat=latitude, lng=longitude)
        self._tz = ZoneInfo(self._tz_name)

        # Offset belirleme
        if offsets is not None:
            self.offsets = offsets
        elif auto_diyanet_offsets and self.is_in_turkey:
            self.offsets = DIYANET_OFFSETS
        else:
            self.offsets = PrayerOffsets()

    @property
    def is_in_turkey(self) -> bool:
        """Koordinatlar Türkiye'de mi?"""
        return self._tz_name in TURKEY_TIMEZONES

    @property
    def timezone_offset(self) -> int:
        """UTC offset saat cinsinden"""
        now = datetime.now(self._tz)
        return int(now.utcoffset().total_seconds() / 3600)

    def _apply_offset(self, time_obj, target_date: date, minutes: int) -> str:
        dt = datetime.combine(target_date, time_obj)
        adjusted = dt + timedelta(minutes=minutes, seconds=self.rounding_seconds)
        return adjusted.strftime("%H:%M")

    def calculate(self, target_date: date) -> PrayerTimes:
        """Belirtilen tarih için namaz vakitlerini hesapla"""
        conf = PrayerConf(
            self.longitude,
            self.latitude,
            self.timezone_offset,
            self.fajr_isha_method,
            self.asr_fiqh,
        )
        prayer = Prayer(conf, target_date)

        return PrayerTimes(
            imsak=self._apply_offset(
                prayer.fajr_time(), target_date, self.offsets.fajr
            ),
            gunes=self._apply_offset(
                prayer.sherook_time(), target_date, self.offsets.sunrise
            ),
            ogle=self._apply_offset(
                prayer.dohr_time(), target_date, self.offsets.dhuhr
            ),
            ikindi=self._apply_offset(prayer.asr_time(), target_date, self.offsets.asr),
            aksam=self._apply_offset(
                prayer.maghreb_time(), target_date, self.offsets.maghrib
            ),
            yatsi=self._apply_offset(
                prayer.ishaa_time(), target_date, self.offsets.isha
            ),
        )

    def calculate_range(
        self, start_date: date, days: int
    ) -> list[tuple[date, PrayerTimes]]:
        """Belirtilen tarihten itibaren n gün için vakitleri hesapla"""
        return [
            (
                start_date + timedelta(days=i),
                self.calculate(start_date + timedelta(days=i)),
            )
            for i in range(days)
        ]


# Kullanım
if __name__ == "__main__":
    # Türkiye'de -> otomatik DIYANET_OFFSETS
    calc = PrayerTimeCalculator(
        latitude=41.17884530097103, longitude=28.884060058956717
    )

    print(f"Türkiye'de mi: {calc.is_in_turkey}")  # True
    print(f"Uygulanan offset: {calc.offsets}")  # DIYANET_OFFSETS

    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()

    print("=" * 75)
    print(f"{'İSTANBUL 30 GÜNLÜK İMSAKİYE':^75}")
    print("=" * 75)
    print(
        f"{'Tarih':<12} {'İmsak':>7} {'Güneş':>7} {'Öğle':>7} {'İkindi':>7} {'Akşam':>7} {'Yatsı':>7}"
    )
    print("-" * 75)

    for current_date, times in calc.calculate_range(today, 31):
        day_name = format_date(current_date, "dd.MM EEE", locale="tr_TR")
        print(
            f"{day_name:<12} {times.imsak:>7} {times.gunes:>7} {times.ogle:>7} "
            f"{times.ikindi:>7} {times.aksam:>7} {times.yatsi:>7}"
        )

    print("=" * 75)
