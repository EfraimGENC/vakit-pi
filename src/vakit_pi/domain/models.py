"""Domain models and value objects."""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Self


class PrayerName(str, Enum):
    """Namaz vakti isimleri."""

    FAJR = "imsak"
    SUNRISE = "gunes"
    DHUHR = "ogle"
    ASR = "ikindi"
    MAGHRIB = "aksam"
    ISHA = "yatsi"

    @property
    def display_name(self) -> str:
        """Türkçe görüntüleme adı."""
        names = {
            PrayerName.FAJR: "İmsak",
            PrayerName.SUNRISE: "Güneş",
            PrayerName.DHUHR: "Öğle",
            PrayerName.ASR: "İkindi",
            PrayerName.MAGHRIB: "Akşam",
            PrayerName.ISHA: "Yatsı",
        }
        return names[self]

    @property
    def icon(self) -> str:
        """Emoji ikonu."""
        icons = {
            PrayerName.FAJR: "🌙",
            PrayerName.SUNRISE: "🌅",
            PrayerName.DHUHR: "☀️",
            PrayerName.ASR: "🌤️",
            PrayerName.MAGHRIB: "🌇",
            PrayerName.ISHA: "🌃",
        }
        return icons[self]


class AdhanType(str, Enum):
    """Ezan türleri."""

    MAKKAH = "makkah"
    MADINAH = "madinah"
    ISTANBUL = "istanbul"

    @property
    def display_name(self) -> str:
        """Türkçe görüntüleme adı."""
        names = {
            AdhanType.MAKKAH: "Mekke Ezanı",
            AdhanType.MADINAH: "Medine Ezanı",
            AdhanType.ISTANBUL: "İstanbul Ezanı",
        }
        return names[self]

    @property
    def filename(self) -> str:
        """Ezan ses dosyası adı."""
        return f"adhan_{self.value}.mp3"


@dataclass(frozen=True)
class Location:
    """Konum bilgisi (immutable value object)."""

    latitude: float
    longitude: float
    city: str = ""

    def __post_init__(self) -> None:
        """Koordinat doğrulaması."""
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Geçersiz enlem: {self.latitude}")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Geçersiz boylam: {self.longitude}")


@dataclass(frozen=True)
class PrayerOffsets:
    """Namaz vakitlerine uygulanacak offset değerleri (dakika)."""

    fajr: int = 0
    sunrise: int = 0
    dhuhr: int = 0
    asr: int = 0
    maghrib: int = 0
    isha: int = 0

    def get_offset(self, prayer: PrayerName) -> int:
        """Belirtilen vakit için offset döndür."""
        mapping = {
            PrayerName.FAJR: self.fajr,
            PrayerName.SUNRISE: self.sunrise,
            PrayerName.DHUHR: self.dhuhr,
            PrayerName.ASR: self.asr,
            PrayerName.MAGHRIB: self.maghrib,
            PrayerName.ISHA: self.isha,
        }
        return mapping[prayer]


# Diyanet'in kullandığı temkin süreleri
DIYANET_OFFSETS = PrayerOffsets(fajr=0, sunrise=-7, dhuhr=5, asr=4, maghrib=7, isha=0)


@dataclass(frozen=True)
class PrayerTime:
    """Tek bir namaz vakti."""

    name: PrayerName
    time: time
    date: date

    @property
    def datetime(self) -> datetime:
        """Datetime olarak döndür."""
        return datetime.combine(self.date, self.time)

    @property
    def time_str(self) -> str:
        """HH:MM formatında."""
        return self.time.strftime("%H:%M")


@dataclass(frozen=True)
class PrayerTimes:
    """Bir günün tüm namaz vakitleri."""

    date: date
    fajr: time
    sunrise: time
    dhuhr: time
    asr: time
    maghrib: time
    isha: time

    def get_time(self, prayer: PrayerName) -> time:
        """Belirtilen vaktin saatini döndür."""
        mapping = {
            PrayerName.FAJR: self.fajr,
            PrayerName.SUNRISE: self.sunrise,
            PrayerName.DHUHR: self.dhuhr,
            PrayerName.ASR: self.asr,
            PrayerName.MAGHRIB: self.maghrib,
            PrayerName.ISHA: self.isha,
        }
        return mapping[prayer]

    def get_prayer_time(self, prayer: PrayerName) -> PrayerTime:
        """PrayerTime nesnesi olarak döndür."""
        return PrayerTime(name=prayer, time=self.get_time(prayer), date=self.date)

    def all_prayer_times(self) -> list[PrayerTime]:
        """Tüm vakitleri sıralı liste olarak döndür."""
        return [self.get_prayer_time(prayer) for prayer in PrayerName]

    def to_dict(self) -> dict[str, str]:
        """Dictionary olarak döndür."""
        return {
            "date": self.date.isoformat(),
            "imsak": self.fajr.strftime("%H:%M"),
            "gunes": self.sunrise.strftime("%H:%M"),
            "ogle": self.dhuhr.strftime("%H:%M"),
            "ikindi": self.asr.strftime("%H:%M"),
            "aksam": self.maghrib.strftime("%H:%M"),
            "yatsi": self.isha.strftime("%H:%M"),
        }


@dataclass
class VolumeSettings:
    """Vakit bazlı ses seviyesi ayarları."""

    default: int = 80
    fajr: int | None = None
    sunrise: int | None = None
    dhuhr: int | None = None
    asr: int | None = None
    maghrib: int | None = None
    isha: int | None = None

    def __post_init__(self) -> None:
        """Ses seviyesi doğrulaması."""
        for name, value in [
            ("default", self.default),
            ("fajr", self.fajr),
            ("sunrise", self.sunrise),
            ("dhuhr", self.dhuhr),
            ("asr", self.asr),
            ("maghrib", self.maghrib),
            ("isha", self.isha),
        ]:
            if value is not None and not 0 <= value <= 100:
                raise ValueError(f"Geçersiz ses seviyesi ({name}): {value}")

    def get_volume(self, prayer: PrayerName) -> int:
        """Belirtilen vakit için ses seviyesini döndür."""
        mapping = {
            PrayerName.FAJR: self.fajr,
            PrayerName.SUNRISE: self.sunrise,
            PrayerName.DHUHR: self.dhuhr,
            PrayerName.ASR: self.asr,
            PrayerName.MAGHRIB: self.maghrib,
            PrayerName.ISHA: self.isha,
        }
        specific_volume = mapping[prayer]
        return specific_volume if specific_volume is not None else self.default

    def to_dict(self) -> dict[str, int | None]:
        """Dictionary olarak döndür."""
        return {
            "default": self.default,
            "fajr": self.fajr,
            "sunrise": self.sunrise,
            "dhuhr": self.dhuhr,
            "asr": self.asr,
            "maghrib": self.maghrib,
            "isha": self.isha,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int | None]) -> Self:
        """Dictionary'den oluştur."""
        return cls(
            default=data.get("default", 80) or 80,
            fajr=data.get("fajr"),
            sunrise=data.get("sunrise"),
            dhuhr=data.get("dhuhr"),
            asr=data.get("asr"),
            maghrib=data.get("maghrib"),
            isha=data.get("isha"),
        )


@dataclass
class PrayerSettings:
    """Namaz/ezan ayarları."""

    location: Location
    adhan_type: AdhanType = AdhanType.ISTANBUL
    offsets: PrayerOffsets = field(default_factory=lambda: DIYANET_OFFSETS)
    volume: VolumeSettings = field(default_factory=VolumeSettings)
    enabled_prayers: set[PrayerName] = field(
        default_factory=lambda: {
            PrayerName.FAJR,
            PrayerName.DHUHR,
            PrayerName.ASR,
            PrayerName.MAGHRIB,
            PrayerName.ISHA,
        }
    )
    pre_alert_minutes: int = 0
    fajr_isha_method: int = 2  # Diyanet metodu
    asr_fiqh: int = 1  # Hanefi mezhebi

    def is_prayer_enabled(self, prayer: PrayerName) -> bool:
        """Belirtilen vakit için ezan aktif mi?"""
        return prayer in self.enabled_prayers

    def to_dict(self) -> dict:
        """Dictionary olarak döndür."""
        return {
            "location": {
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "city": self.location.city,
            },
            "adhan_type": self.adhan_type.value,
            "offsets": {
                "fajr": self.offsets.fajr,
                "sunrise": self.offsets.sunrise,
                "dhuhr": self.offsets.dhuhr,
                "asr": self.offsets.asr,
                "maghrib": self.offsets.maghrib,
                "isha": self.offsets.isha,
            },
            "volume": self.volume.to_dict(),
            "enabled_prayers": [p.value for p in self.enabled_prayers],
            "pre_alert_minutes": self.pre_alert_minutes,
            "fajr_isha_method": self.fajr_isha_method,
            "asr_fiqh": self.asr_fiqh,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Dictionary'den oluştur."""
        location_data = data.get("location", {})
        return cls(
            location=Location(
                latitude=location_data.get("latitude", 41.0),
                longitude=location_data.get("longitude", 29.0),
                city=location_data.get("city", ""),
            ),
            adhan_type=AdhanType(data.get("adhan_type", AdhanType.ISTANBUL.value)),
            offsets=PrayerOffsets(
                fajr=data.get("offsets", {}).get("fajr", 0),
                sunrise=data.get("offsets", {}).get("sunrise", -7),
                dhuhr=data.get("offsets", {}).get("dhuhr", 5),
                asr=data.get("offsets", {}).get("asr", 4),
                maghrib=data.get("offsets", {}).get("maghrib", 7),
                isha=data.get("offsets", {}).get("isha", 0),
            ),
            volume=VolumeSettings.from_dict(data.get("volume", {})),
            enabled_prayers={
                PrayerName(p)
                for p in data.get("enabled_prayers", ["imsak", "ogle", "ikindi", "aksam", "yatsi"])
            },
            pre_alert_minutes=data.get("pre_alert_minutes", 0),
            fajr_isha_method=data.get("fajr_isha_method", 2),
            asr_fiqh=data.get("asr_fiqh", 1),
        )
