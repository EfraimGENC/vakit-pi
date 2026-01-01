"""API Routes."""

from datetime import datetime, timedelta
from typing import Annotated

from babel.dates import format_date
from fastapi import APIRouter, Depends, HTTPException, status

from vakit_pi import __version__
from vakit_pi.api.dependencies import AppState, get_app_state
from vakit_pi.api.schemas import (
    ApiResponse,
    CurrentStateSchema,
    LocationSchema,
    PrayerOffsetsSchema,
    PrayerTimeSchema,
    PrayerTimesSchema,
    ScheduledJobSchema,
    SettingsSchema,
    SettingsUpdateSchema,
    SystemStatusSchema,
    TestAudioRequest,
    VolumeSettingsSchema,
)
from vakit_pi.domain.models import (
    AdhanType,
    Location,
    PrayerName,
    PrayerOffsets,
    PrayerSettings,
    VolumeSettings,
)

router = APIRouter()


def _format_timedelta(td: timedelta) -> str:
    """Timedelta'yı okunabilir formata çevir."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _get_hijri_date(gregorian: datetime) -> str:
    """Basit Hicri tarih hesaplama (yaklaşık)."""
    jd = int((gregorian.timestamp() / 86400) + 2440587.5)
    l_val = jd - 1948440 + 10632
    n = (l_val - 1) // 10631
    l2 = l_val - 10631 * n + 354
    j = ((10985 - l2) // 5316) * ((50 * l2) // 17719) + (l2 // 5670) * ((43 * l2) // 15238)
    l3 = l2 - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
    month = (24 * l3) // 709
    day = l3 - (709 * month) // 24
    year = 30 * n + j - 30

    months = [
        "Muharrem",
        "Safer",
        "Rebiülevvel",
        "Rebiülahir",
        "Cemaziyelevvel",
        "Cemaziyelahir",
        "Recep",
        "Şaban",
        "Ramazan",
        "Şevval",
        "Zilkade",
        "Zilhicce",
    ]
    return f"{day} {months[month - 1]} {year}"


# ============== State & Status ==============


@router.get("/status", response_model=SystemStatusSchema)
async def get_status(state: Annotated[AppState, Depends(get_app_state)]) -> SystemStatusSchema:
    """Sistem durumunu getir."""
    uptime = datetime.now() - state.started_at
    jobs = state.scheduler_service.get_scheduled_jobs()

    return SystemStatusSchema(
        version=__version__,
        uptime=str(uptime).split(".")[0],
        scheduler_running=state.scheduler_adapter._started,
        scheduled_jobs_count=len(jobs),
        audio_player=state.audio_player.__class__.__name__,
        settings_path=str(state.settings_repository.file_path),
    )


@router.get("/current", response_model=CurrentStateSchema)
async def get_current_state(
    state: Annotated[AppState, Depends(get_app_state)],
) -> CurrentStateSchema:
    """Mevcut durumu getir (saat, vakit, geri sayım vb.)."""
    now = datetime.now(state.prayer_service.timezone)
    current = state.prayer_service.get_current_prayer(now)
    next_prayer = state.prayer_service.get_next_prayer(now)
    time_until = state.prayer_service.get_time_until_next_prayer(now)

    return CurrentStateSchema(
        current_time=now.strftime("%H:%M:%S"),
        current_date=format_date(now, "d MMMM yyyy, EEEE", locale="tr_TR"),
        hijri_date=_get_hijri_date(now),
        location=LocationSchema(
            latitude=state.settings.location.latitude,
            longitude=state.settings.location.longitude,
            city=state.settings.location.city,
        ),
        current_prayer=current,
        current_prayer_display=current.display_name,
        next_prayer=next_prayer.name,
        next_prayer_display=next_prayer.name.display_name,
        next_prayer_time=next_prayer.time_str,
        countdown=_format_timedelta(time_until),
        is_adhan_playing=state.adhan_service.is_playing(),
    )


# ============== Prayer Times ==============


@router.get("/times/today", response_model=PrayerTimesSchema)
async def get_today_times(state: Annotated[AppState, Depends(get_app_state)]) -> PrayerTimesSchema:
    """Bugünün namaz vakitlerini getir."""
    now = datetime.now(state.prayer_service.timezone)
    times = state.prayer_service.calculate(now.date())

    prayers = []
    for prayer in PrayerName:
        prayers.append(
            PrayerTimeSchema(
                name=prayer,
                display_name=prayer.display_name,
                icon=prayer.icon,
                time=times.get_time(prayer).strftime("%H:%M"),
                enabled=state.settings.is_prayer_enabled(prayer),
            )
        )

    return PrayerTimesSchema(
        date=times.date,
        date_formatted=format_date(now, "d MMMM yyyy, EEEE", locale="tr_TR"),
        hijri_date=_get_hijri_date(now),
        prayers=prayers,
    )


@router.get("/times/week", response_model=list[PrayerTimesSchema])
async def get_week_times(
    state: Annotated[AppState, Depends(get_app_state)],
) -> list[PrayerTimesSchema]:
    """Haftalık namaz vakitlerini getir."""
    now = datetime.now(state.prayer_service.timezone)
    week_times = state.prayer_service.calculate_range(now.date(), 7)

    result = []
    for times in week_times:
        day_dt = datetime.combine(times.date, datetime.min.time())
        prayers = []
        for prayer in PrayerName:
            prayers.append(
                PrayerTimeSchema(
                    name=prayer,
                    display_name=prayer.display_name,
                    icon=prayer.icon,
                    time=times.get_time(prayer).strftime("%H:%M"),
                    enabled=state.settings.is_prayer_enabled(prayer),
                )
            )
        result.append(
            PrayerTimesSchema(
                date=times.date,
                date_formatted=format_date(day_dt, "d MMMM yyyy, EEEE", locale="tr_TR"),
                hijri_date=_get_hijri_date(day_dt),
                prayers=prayers,
            )
        )

    return result


# ============== Settings ==============


@router.get("/settings", response_model=SettingsSchema)
async def get_settings(state: Annotated[AppState, Depends(get_app_state)]) -> SettingsSchema:
    """Mevcut ayarları getir."""
    s = state.settings
    return SettingsSchema(
        location=LocationSchema(
            latitude=s.location.latitude,
            longitude=s.location.longitude,
            city=s.location.city,
        ),
        adhan_type=s.adhan_type,
        offsets=PrayerOffsetsSchema(
            fajr=s.offsets.fajr,
            sunrise=s.offsets.sunrise,
            dhuhr=s.offsets.dhuhr,
            asr=s.offsets.asr,
            maghrib=s.offsets.maghrib,
            isha=s.offsets.isha,
        ),
        volume=VolumeSettingsSchema(
            default=s.volume.default,
            fajr=s.volume.fajr,
            sunrise=s.volume.sunrise,
            dhuhr=s.volume.dhuhr,
            asr=s.volume.asr,
            maghrib=s.volume.maghrib,
            isha=s.volume.isha,
        ),
        enabled_prayers=list(s.enabled_prayers),
        pre_alert_minutes=s.pre_alert_minutes,
        fajr_isha_method=s.fajr_isha_method,
        asr_fiqh=s.asr_fiqh,
    )


@router.put("/settings", response_model=ApiResponse)
async def update_settings(
    update: SettingsUpdateSchema,
    state: Annotated[AppState, Depends(get_app_state)],
) -> ApiResponse:
    """Ayarları güncelle."""
    current = state.settings

    # Partial update
    new_location = current.location
    if update.location:
        new_location = Location(
            latitude=update.location.latitude,
            longitude=update.location.longitude,
            city=update.location.city,
        )

    new_offsets = current.offsets
    if update.offsets:
        new_offsets = PrayerOffsets(
            fajr=update.offsets.fajr,
            sunrise=update.offsets.sunrise,
            dhuhr=update.offsets.dhuhr,
            asr=update.offsets.asr,
            maghrib=update.offsets.maghrib,
            isha=update.offsets.isha,
        )

    new_volume = current.volume
    if update.volume:
        new_volume = VolumeSettings(
            default=update.volume.default,
            fajr=update.volume.fajr,
            sunrise=update.volume.sunrise,
            dhuhr=update.volume.dhuhr,
            asr=update.volume.asr,
            maghrib=update.volume.maghrib,
            isha=update.volume.isha,
        )

    new_settings = PrayerSettings(
        location=new_location,
        adhan_type=update.adhan_type or current.adhan_type,
        offsets=new_offsets,
        volume=new_volume,
        enabled_prayers=set(update.enabled_prayers)
        if update.enabled_prayers
        else current.enabled_prayers,
        pre_alert_minutes=update.pre_alert_minutes
        if update.pre_alert_minutes is not None
        else current.pre_alert_minutes,
        fajr_isha_method=update.fajr_isha_method
        if update.fajr_isha_method is not None
        else current.fajr_isha_method,
        asr_fiqh=update.asr_fiqh if update.asr_fiqh is not None else current.asr_fiqh,
    )

    # Update state and services
    state.settings = new_settings
    state.prayer_service.update_location(new_location)
    state.prayer_service.update_offsets(new_offsets)
    state.adhan_service.update_settings(new_settings)

    # Save and reschedule
    await state.settings_repository.save(new_settings)
    state.scheduler_service.reschedule()

    return ApiResponse(success=True, message="Ayarlar güncellendi.")


# ============== Scheduler ==============


@router.get("/scheduler/jobs", response_model=list[ScheduledJobSchema])
async def get_scheduled_jobs(
    state: Annotated[AppState, Depends(get_app_state)],
) -> list[ScheduledJobSchema]:
    """Planlanmış işleri listele."""
    jobs = state.scheduler_service.get_scheduled_jobs()
    return [
        ScheduledJobSchema(
            job_id=job_id,
            run_time=run_time.strftime("%Y-%m-%d %H:%M:%S"),
            prayer=job_id.split("_")[1] if "_" in job_id else "unknown",
        )
        for job_id, run_time in jobs
    ]


@router.post("/scheduler/reschedule", response_model=ApiResponse)
async def reschedule(state: Annotated[AppState, Depends(get_app_state)]) -> ApiResponse:
    """Tüm planlamaları yeniden yap."""
    count = state.scheduler_service.reschedule()
    return ApiResponse(
        success=True,
        message=f"{count} iş yeniden planlandı.",
        data={"scheduled_count": count},
    )


# ============== Audio ==============


@router.post("/audio/test", response_model=ApiResponse)
async def test_audio(
    request: TestAudioRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> ApiResponse:
    """Ses testi yap. Test sırasında /audio/stop ile durdurulabilir."""
    success = await state.adhan_service.test_audio(request.volume, request.duration)
    if success:
        return ApiResponse(success=True, message="Ses testi tamamlandı.")
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ses testi başarısız. Ezan dosyası veya ses cihazı kontrol edin.",
        )


@router.post("/audio/stop", response_model=ApiResponse)
async def stop_audio(state: Annotated[AppState, Depends(get_app_state)]) -> ApiResponse:
    """Çalan sesi durdur."""
    await state.adhan_service.stop_adhan()
    return ApiResponse(success=True, message="Ses durduruldu.")


@router.get("/audio/playing")
async def get_audio_playing_status(
    state: Annotated[AppState, Depends(get_app_state)],
) -> dict[str, bool]:
    """Ezan çalıp çalmadığını kontrol et. Hafif endpoint."""
    return {"is_playing": state.adhan_service.is_playing()}


@router.get("/audio/adhan-types")
async def get_adhan_types() -> list[dict[str, str]]:
    """Kullanılabilir ezan türlerini listele."""
    return [{"value": t.value, "label": t.display_name} for t in AdhanType]


# ============== Utility ==============


@router.get("/prayers")
async def get_prayer_names() -> list[dict[str, str]]:
    """Namaz vakti isimlerini listele."""
    return [{"value": p.value, "display_name": p.display_name, "icon": p.icon} for p in PrayerName]
