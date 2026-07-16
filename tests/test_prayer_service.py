"""Tests for prayer service."""

from datetime import date, datetime, time

import pytest

from vakit_pi.domain.models import Location, PrayerName, PrayerOffsets, DIYANET_OFFSETS
from vakit_pi.services.prayer_service import PrayerService


class TestPrayerService:
    """Prayer service tests."""

    @pytest.fixture
    def istanbul_location(self) -> Location:
        """Istanbul location."""
        return Location(latitude=41.0082, longitude=28.9784, city="İstanbul")

    @pytest.fixture
    def service(self, istanbul_location: Location) -> PrayerService:
        """Create prayer service."""
        return PrayerService(location=istanbul_location)

    def test_is_in_turkey(self, service: PrayerService) -> None:
        """Test Turkey detection."""
        assert service.is_in_turkey is True

    def test_timezone(self, service: PrayerService) -> None:
        """Test timezone detection."""
        assert service.timezone_name in ("Europe/Istanbul", "Asia/Istanbul")

    def test_auto_diyanet_offsets(self, service: PrayerService) -> None:
        """Test automatic Diyanet offsets for Turkey."""
        assert service.offsets == DIYANET_OFFSETS

    def test_calculate_today(self, service: PrayerService) -> None:
        """Test calculating today's prayer times."""
        today = date.today()
        times = service.calculate(today)

        assert times.date == today
        assert times.fajr < times.sunrise
        assert times.sunrise < times.dhuhr
        assert times.dhuhr < times.asr
        assert times.asr < times.maghrib
        assert times.maghrib < times.isha

    def test_calculate_range(self, service: PrayerService) -> None:
        """Test calculating multiple days."""
        today = date.today()
        times_list = service.calculate_range(today, 7)

        assert len(times_list) == 7
        assert times_list[0].date == today

    def test_get_current_prayer(self, service: PrayerService) -> None:
        """Test getting current prayer."""
        # Create a datetime at noon
        noon = datetime.now(service.timezone).replace(
            hour=12, minute=30, second=0, microsecond=0
        )
        current = service.get_current_prayer(noon)

        # At noon, it should be Dhuhr (after noon prayer time)
        # or Sunrise (before noon prayer time)
        assert current in (PrayerName.DHUHR, PrayerName.SUNRISE)

    def test_get_next_prayer(self, service: PrayerService) -> None:
        """Test getting next prayer."""
        now = datetime.now(service.timezone)
        next_prayer = service.get_next_prayer(now)

        assert next_prayer.name in PrayerName
        assert next_prayer.date >= now.date()

    def test_time_until_next_prayer(self, service: PrayerService) -> None:
        """Test time until next prayer."""
        now = datetime.now(service.timezone)
        time_until = service.get_time_until_next_prayer(now)

        # Should be positive
        assert time_until.total_seconds() > 0

    def test_custom_offsets(self, istanbul_location: Location) -> None:
        """Test custom offsets."""
        custom_offsets = PrayerOffsets(fajr=5, dhuhr=10)
        service = PrayerService(
            location=istanbul_location,
            offsets=custom_offsets,
            auto_diyanet_offsets=False,
        )

        assert service.offsets == custom_offsets

    def test_non_turkey_location(self) -> None:
        """Test non-Turkey location."""
        london = Location(latitude=51.5074, longitude=-0.1278, city="London")
        service = PrayerService(location=london)

        assert service.is_in_turkey is False
        assert service.offsets == PrayerOffsets()  # Default, not Diyanet

    def test_update_location(self, service: PrayerService) -> None:
        """Test updating location."""
        new_loc = Location(latitude=39.9334, longitude=32.8597, city="Ankara")
        service.update_location(new_loc)

        assert service.location == new_loc
        assert service.is_in_turkey is True
