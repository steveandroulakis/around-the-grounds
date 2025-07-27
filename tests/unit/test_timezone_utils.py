"""Tests for timezone utilities."""

from datetime import datetime, timezone
from unittest.mock import patch, Mock

# ZoneInfo not used in this test file

from around_the_grounds.utils.timezone_utils import (
    PACIFIC_TZ,
    now_in_pacific,
    now_in_pacific_naive,
    make_pacific_naive,
    utc_to_pacific_naive,
    parse_date_with_pacific_context,
    get_pacific_year,
    get_pacific_month,
    get_pacific_day,
    is_dst_transition_date,
    format_time_with_timezone,
)


class TestPacificTimezone:
    """Test Pacific timezone handling."""

    def test_pacific_tz_constant(self) -> None:
        """Test that PACIFIC_TZ is correctly configured."""
        assert PACIFIC_TZ.key == "America/Los_Angeles"

    def test_now_in_pacific(self) -> None:
        """Test getting current time in Pacific timezone."""
        pacific_time = now_in_pacific()
        assert pacific_time.tzinfo == PACIFIC_TZ

    def test_now_in_pacific_naive(self) -> None:
        """Test getting current time in Pacific timezone as naive."""
        pacific_naive = now_in_pacific_naive()
        assert pacific_naive.tzinfo is None

    def test_make_pacific_naive(self) -> None:
        """Test making a naive datetime Pacific."""
        dt = datetime(2025, 7, 15, 14, 30)
        result = make_pacific_naive(dt)
        assert result == dt
        assert result.tzinfo is None

    def test_utc_to_pacific_naive_with_timezone_aware(self) -> None:
        """Test converting UTC to Pacific naive with timezone-aware input."""
        # January (PST) - UTC-8
        utc_dt = datetime(2025, 1, 15, 22, 30, tzinfo=timezone.utc)
        pacific_naive = utc_to_pacific_naive(utc_dt)

        assert pacific_naive.tzinfo is None
        assert pacific_naive.hour == 14  # 22 UTC - 8 hours = 14 PST
        assert pacific_naive.day == 15

    def test_utc_to_pacific_naive_with_naive_input(self) -> None:
        """Test converting UTC to Pacific naive with naive input (assumed UTC)."""
        # July (PDT) - UTC-7
        utc_dt = datetime(2025, 7, 15, 21, 30)  # Naive, assumed UTC
        pacific_naive = utc_to_pacific_naive(utc_dt)

        assert pacific_naive.tzinfo is None
        assert pacific_naive.hour == 14  # 21 UTC - 7 hours = 14 PDT
        assert pacific_naive.day == 15

    def test_parse_date_with_pacific_context(self) -> None:
        """Test parsing date with Pacific timezone context."""
        with patch(
            "around_the_grounds.utils.timezone_utils.now_in_pacific_naive"
        ) as mock_now:
            mock_now.return_value = datetime(2025, 7, 15, 14, 30)

            # Use defaults (current Pacific time)
            result = parse_date_with_pacific_context()
            assert result.year == 2025
            assert result.month == 7
            assert result.day == 15

            # Use specific values
            result = parse_date_with_pacific_context(2024, 12, 25)
            assert result.year == 2024
            assert result.month == 12
            assert result.day == 25

    @patch("around_the_grounds.utils.timezone_utils.now_in_pacific_naive")
    def test_get_pacific_time_components(self, mock_now: Mock) -> None:
        """Test getting Pacific time components."""
        mock_now.return_value = datetime(2025, 7, 15, 14, 30, 45)

        assert get_pacific_year() == 2025
        assert get_pacific_month() == 7
        assert get_pacific_day() == 15


class TestDSTTransitions:
    """Test Daylight Saving Time transition handling."""

    def test_is_dst_transition_date_spring_forward(self) -> None:
        """Test DST transition detection for Spring Forward (PST->PDT)."""
        # March 9, 2025 is Spring Forward in Pacific timezone
        spring_forward = datetime(2025, 3, 9)
        assert is_dst_transition_date(spring_forward)

    def test_is_dst_transition_date_fall_back(self) -> None:
        """Test DST transition detection for Fall Back (PDT->PST)."""
        # November 2, 2025 is Fall Back in Pacific timezone
        fall_back = datetime(2025, 11, 2)
        assert is_dst_transition_date(fall_back)

    def test_is_dst_transition_date_normal_day(self) -> None:
        """Test DST transition detection for normal days."""
        normal_day = datetime(2025, 7, 15)
        assert not is_dst_transition_date(normal_day)

    def test_utc_to_pacific_dst_transitions(self) -> None:
        """Test UTC to Pacific conversion during DST transitions."""
        # Spring Forward: 2:00 AM PST becomes 3:00 AM PDT (2025-03-09)
        # 9:00 UTC should become 1:00 AM PST (before transition)
        utc_before = datetime(2025, 3, 9, 9, 0, tzinfo=timezone.utc)
        pacific_before = utc_to_pacific_naive(utc_before)
        assert pacific_before.hour == 1  # PST (UTC-8)

        # 11:00 UTC should become 4:00 AM PDT (after transition)
        utc_after = datetime(2025, 3, 9, 11, 0, tzinfo=timezone.utc)
        pacific_after = utc_to_pacific_naive(utc_after)
        assert pacific_after.hour == 4  # PDT (UTC-7), 2-3 AM is skipped


class TestTimeFormatting:
    """Test time formatting utilities."""

    def test_format_time_with_timezone_with_indicator(self) -> None:
        """Test formatting time with timezone indicator."""
        dt = datetime(2025, 7, 15, 14, 30)
        result = format_time_with_timezone(dt, include_timezone=True)
        assert result == "2:30 PM PT"

    def test_format_time_with_timezone_without_indicator(self) -> None:
        """Test formatting time without timezone indicator."""
        dt = datetime(2025, 7, 15, 14, 30)
        result = format_time_with_timezone(dt, include_timezone=False)
        assert result == "2:30 PM"

    def test_format_time_with_timezone_midnight(self) -> None:
        """Test formatting midnight time."""
        dt = datetime(2025, 7, 15, 0, 0)
        result = format_time_with_timezone(dt, include_timezone=True)
        assert result == "12:00 AM PT"

    def test_format_time_with_timezone_noon(self) -> None:
        """Test formatting noon time."""
        dt = datetime(2025, 7, 15, 12, 0)
        result = format_time_with_timezone(dt, include_timezone=True)
        assert result == "12:00 PM PT"

    def test_format_time_strips_leading_zero(self) -> None:
        """Test that leading zero is stripped from hour."""
        dt = datetime(2025, 7, 15, 9, 5)  # 09:05 AM
        result = format_time_with_timezone(dt, include_timezone=True)
        assert result == "9:05 AM PT"
        assert not result.startswith("0")


class TestTimezoneIntegration:
    """Test integration scenarios with different timezones."""

    def test_cross_timezone_consistency(self) -> None:
        """Test that Pacific time is consistent regardless of system timezone."""
        # This test ensures our utilities work the same way regardless of
        # what timezone the server is running in

        # Create a UTC datetime
        utc_time = datetime(2025, 7, 15, 21, 30, tzinfo=timezone.utc)

        # Convert to Pacific (should be 2:30 PM PDT)
        pacific_time = utc_to_pacific_naive(utc_time)

        assert pacific_time.hour == 14  # 2 PM
        assert pacific_time.minute == 30
        assert pacific_time.tzinfo is None

    def test_year_rollover_in_pacific_context(self) -> None:
        """Test year calculations use Pacific timezone context."""
        # Mock a time where Pacific and UTC are in different years
        # December 31, 2024 10:00 PM PST = January 1, 2025 6:00 AM UTC

        with patch(
            "around_the_grounds.utils.timezone_utils.now_in_pacific_naive"
        ) as mock_now:
            mock_now.return_value = datetime(2024, 12, 31, 22, 0)  # 10 PM PST

            year = get_pacific_year()
            month = get_pacific_month()
            day = get_pacific_day()

            # Should use Pacific time (still 2024)
            assert year == 2024
            assert month == 12
            assert day == 31
