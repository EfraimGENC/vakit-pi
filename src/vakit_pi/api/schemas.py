"""Pydantic schemas for API."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from vakit_pi.domain.models import AdhanType, PrayerName


class LocationSchema(BaseModel):
    """Konum şeması."""

    latitude: Annotated[float, Field(ge=-90, le=90, description="Enlem")]
    longitude: Annotated[float, Field(ge=-180, le=180, description="Boylam")]
    city: str = Field(default="", description="Şehir adı")


class PrayerOffsetsSchema(BaseModel):
    """Temkin süreleri şeması."""

    fajr: int = Field(default=0, description="İmsak offset (dakika)")
    sunrise: int = Field(default=-7, description="Güneş offset (dakika)")
    dhuhr: int = Field(default=5, description="Öğle offset (dakika)")
    asr: int = Field(default=4, description="İkindi offset (dakika)")
    maghrib: int = Field(default=7, description="Akşam offset (dakika)")
    isha: int = Field(default=0, description="Yatsı offset (dakika)")


class VolumeSettingsSchema(BaseModel):
    """Ses seviyesi ayarları şeması."""

    default: Annotated[int, Field(ge=0, le=100, default=80)]
    fajr: Annotated[int | None, Field(ge=0, le=100, default=None)]
    sunrise: Annotated[int | None, Field(ge=0, le=100, default=None)]
    dhuhr: Annotated[int | None, Field(ge=0, le=100, default=None)]
    asr: Annotated[int | None, Field(ge=0, le=100, default=None)]
    maghrib: Annotated[int | None, Field(ge=0, le=100, default=None)]
    isha: Annotated[int | None, Field(ge=0, le=100, default=None)]


class SettingsSchema(BaseModel):
    """Tüm ayarlar şeması."""

    location: LocationSchema
    adhan_type: AdhanType = Field(default=AdhanType.ISTANBUL)
    offsets: PrayerOffsetsSchema = Field(default_factory=PrayerOffsetsSchema)
    volume: VolumeSettingsSchema = Field(default_factory=VolumeSettingsSchema)
    enabled_prayers: list[PrayerName] = Field(
        default_factory=lambda: [
            PrayerName.FAJR,
            PrayerName.DHUHR,
            PrayerName.ASR,
            PrayerName.MAGHRIB,
            PrayerName.ISHA,
        ]
    )
    pre_alert_minutes: Annotated[int, Field(ge=0, le=60, default=0)]
    fajr_isha_method: int = Field(default=2, description="Hesaplama metodu")
    asr_fiqh: int = Field(default=1, description="0=Şafi, 1=Hanefi")


class SettingsUpdateSchema(BaseModel):
    """Ayar güncelleme şeması (partial update)."""

    location: LocationSchema | None = None
    adhan_type: AdhanType | None = None
    offsets: PrayerOffsetsSchema | None = None
    volume: VolumeSettingsSchema | None = None
    enabled_prayers: list[PrayerName] | None = None
    pre_alert_minutes: Annotated[int | None, Field(ge=0, le=60)] = None
    fajr_isha_method: int | None = None
    asr_fiqh: int | None = None


class PrayerTimeSchema(BaseModel):
    """Tek namaz vakti şeması."""

    name: PrayerName
    display_name: str
    icon: str
    time: str  # HH:MM formatında
    enabled: bool


class PrayerTimesSchema(BaseModel):
    """Günlük namaz vakitleri şeması."""

    date: date
    date_formatted: str
    hijri_date: str
    prayers: list[PrayerTimeSchema]


class CurrentStateSchema(BaseModel):
    """Mevcut durum şeması."""

    current_time: str
    current_date: str
    hijri_date: str
    location: LocationSchema
    current_prayer: PrayerName
    current_prayer_display: str
    next_prayer: PrayerName
    next_prayer_display: str
    next_prayer_time: str
    countdown: str
    is_adhan_playing: bool


class ScheduledJobSchema(BaseModel):
    """Planlanmış iş şeması."""

    job_id: str
    run_time: str
    prayer: str


class SystemStatusSchema(BaseModel):
    """Sistem durumu şeması."""

    version: str
    uptime: str
    scheduler_running: bool
    scheduled_jobs_count: int
    audio_player: str
    settings_path: str


class TestAudioRequest(BaseModel):
    """Ses testi isteği."""

    volume: Annotated[int | None, Field(ge=0, le=100)] = None


class ApiResponse(BaseModel):
    """Genel API yanıt şeması."""

    success: bool
    message: str
    data: dict | list | None = None
