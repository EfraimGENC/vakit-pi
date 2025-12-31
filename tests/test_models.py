"""Tests for domain models."""

from datetime import date, time

import pytest

from vakit_pi.domain.models import (
    AdhanType,
    Location,
    PrayerName,
    PrayerOffsets,
    PrayerSettings,
    PrayerTime,
    PrayerTimes,
    VolumeSettings,
    DIYANET_OFFSETS,
)


class TestLocation:
    """Location model tests."""

    def test_valid_location(self) -> None:
        """Test valid location creation."""
        loc = Location(latitude=41.0, longitude=29.0, city="İstanbul")
        assert loc.latitude == 41.0
        assert loc.longitude == 29.0
        assert loc.city == "İstanbul"

    def test_invalid_latitude(self) -> None:
        """Test invalid latitude raises error."""
        with pytest.raises(ValueError, match="Geçersiz enlem"):
            Location(latitude=91.0, longitude=29.0)

    def test_invalid_longitude(self) -> None:
        """Test invalid longitude raises error."""
        with pytest.raises(ValueError, match="Geçersiz boylam"):
            Location(latitude=41.0, longitude=181.0)

    def test_location_immutable(self) -> None:
        """Test location is immutable."""
        loc = Location(latitude=41.0, longitude=29.0)
        with pytest.raises(Exception):  # FrozenInstanceError
            loc.latitude = 42.0  # type: ignore


class TestPrayerName:
    """PrayerName enum tests."""

    def test_display_names(self) -> None:
        """Test Turkish display names."""
        assert PrayerName.FAJR.display_name == "İmsak"
        assert PrayerName.DHUHR.display_name == "Öğle"
        assert PrayerName.MAGHRIB.display_name == "Akşam"

    def test_icons(self) -> None:
        """Test prayer icons."""
        assert PrayerName.FAJR.icon == "🌙"
        assert PrayerName.SUNRISE.icon == "🌅"
        assert PrayerName.ISHA.icon == "🌃"


class TestAdhanType:
    """AdhanType enum tests."""

    def test_display_names(self) -> None:
        """Test Turkish display names."""
        assert AdhanType.MAKKAH.display_name == "Mekke Ezanı"
        assert AdhanType.ISTANBUL.display_name == "İstanbul Ezanı"

    def test_filename(self) -> None:
        """Test adhan filenames."""
        assert AdhanType.MAKKAH.filename == "adhan_makkah.mp3"
        assert AdhanType.ISTANBUL.filename == "adhan_istanbul.mp3"


class TestPrayerOffsets:
    """PrayerOffsets tests."""

    def test_default_offsets(self) -> None:
        """Test default offsets are zero."""
        offsets = PrayerOffsets()
        assert offsets.fajr == 0
        assert offsets.dhuhr == 0

    def test_diyanet_offsets(self) -> None:
        """Test Diyanet offsets."""
        assert DIYANET_OFFSETS.sunrise == -7
        assert DIYANET_OFFSETS.dhuhr == 5
        assert DIYANET_OFFSETS.maghrib == 7

    def test_get_offset(self) -> None:
        """Test get_offset method."""
        assert DIYANET_OFFSETS.get_offset(PrayerName.DHUHR) == 5
        assert DIYANET_OFFSETS.get_offset(PrayerName.MAGHRIB) == 7


class TestVolumeSettings:
    """VolumeSettings tests."""

    def test_default_volume(self) -> None:
        """Test default volume."""
        vol = VolumeSettings()
        assert vol.default == 80

    def test_prayer_specific_volume(self) -> None:
        """Test prayer-specific volume."""
        vol = VolumeSettings(default=80, fajr=50)
        assert vol.get_volume(PrayerName.FAJR) == 50
        assert vol.get_volume(PrayerName.DHUHR) == 80  # Uses default

    def test_invalid_volume(self) -> None:
        """Test invalid volume raises error."""
        with pytest.raises(ValueError, match="Geçersiz ses seviyesi"):
            VolumeSettings(default=150)

    def test_to_dict(self) -> None:
        """Test serialization."""
        vol = VolumeSettings(default=80, fajr=50)
        data = vol.to_dict()
        assert data["default"] == 80
        assert data["fajr"] == 50

    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {"default": 70, "fajr": 40}
        vol = VolumeSettings.from_dict(data)
        assert vol.default == 70
        assert vol.fajr == 40


class TestPrayerTime:
    """PrayerTime tests."""

    def test_time_str(self) -> None:
        """Test time string formatting."""
        pt = PrayerTime(
            name=PrayerName.FAJR,
            time=time(5, 30),
            date=date(2024, 1, 1),
        )
        assert pt.time_str == "05:30"

    def test_datetime(self) -> None:
        """Test datetime property."""
        pt = PrayerTime(
            name=PrayerName.FAJR,
            time=time(5, 30),
            date=date(2024, 1, 1),
        )
        dt = pt.datetime
        assert dt.year == 2024
        assert dt.hour == 5
        assert dt.minute == 30


class TestPrayerTimes:
    """PrayerTimes tests."""

    @pytest.fixture
    def sample_times(self) -> PrayerTimes:
        """Create sample prayer times."""
        return PrayerTimes(
            date=date(2024, 1, 1),
            fajr=time(5, 30),
            sunrise=time(7, 0),
            dhuhr=time(12, 30),
            asr=time(15, 15),
            maghrib=time(17, 45),
            isha=time(19, 15),
        )

    def test_get_time(self, sample_times: PrayerTimes) -> None:
        """Test get_time method."""
        assert sample_times.get_time(PrayerName.FAJR) == time(5, 30)
        assert sample_times.get_time(PrayerName.MAGHRIB) == time(17, 45)

    def test_get_prayer_time(self, sample_times: PrayerTimes) -> None:
        """Test get_prayer_time method."""
        pt = sample_times.get_prayer_time(PrayerName.DHUHR)
        assert pt.name == PrayerName.DHUHR
        assert pt.time == time(12, 30)
        assert pt.date == date(2024, 1, 1)

    def test_all_prayer_times(self, sample_times: PrayerTimes) -> None:
        """Test all_prayer_times method."""
        all_times = sample_times.all_prayer_times()
        assert len(all_times) == 6
        assert all_times[0].name == PrayerName.FAJR
        assert all_times[-1].name == PrayerName.ISHA

    def test_to_dict(self, sample_times: PrayerTimes) -> None:
        """Test serialization."""
        data = sample_times.to_dict()
        assert data["imsak"] == "05:30"
        assert data["aksam"] == "17:45"


class TestPrayerSettings:
    """PrayerSettings tests."""

    def test_default_settings(self) -> None:
        """Test default settings."""
        loc = Location(latitude=41.0, longitude=29.0)
        settings = PrayerSettings(location=loc)
        
        assert settings.adhan_type == AdhanType.ISTANBUL
        assert settings.pre_alert_minutes == 0
        assert PrayerName.FAJR in settings.enabled_prayers
        assert PrayerName.SUNRISE not in settings.enabled_prayers

    def test_is_prayer_enabled(self) -> None:
        """Test is_prayer_enabled method."""
        loc = Location(latitude=41.0, longitude=29.0)
        settings = PrayerSettings(
            location=loc,
            enabled_prayers={PrayerName.FAJR, PrayerName.DHUHR},
        )
        
        assert settings.is_prayer_enabled(PrayerName.FAJR) is True
        assert settings.is_prayer_enabled(PrayerName.ASR) is False

    def test_to_dict(self) -> None:
        """Test serialization."""
        loc = Location(latitude=41.0, longitude=29.0, city="İstanbul")
        settings = PrayerSettings(location=loc)
        data = settings.to_dict()
        
        assert data["location"]["latitude"] == 41.0
        assert data["adhan_type"] == "istanbul"
        assert "imsak" in data["enabled_prayers"]

    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {
            "location": {"latitude": 41.0, "longitude": 29.0, "city": "İstanbul"},
            "adhan_type": "makkah",
            "enabled_prayers": ["imsak", "ogle"],
            "volume": {"default": 70},
        }
        settings = PrayerSettings.from_dict(data)
        
        assert settings.location.latitude == 41.0
        assert settings.adhan_type == AdhanType.MAKKAH
        assert settings.is_prayer_enabled(PrayerName.FAJR) is True
        assert settings.is_prayer_enabled(PrayerName.ASR) is False
        assert settings.volume.default == 70
