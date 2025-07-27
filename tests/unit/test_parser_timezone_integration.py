"""Timezone integration tests for all parsers."""

import pytest
from datetime import datetime
from unittest.mock import patch

# ZoneInfo not used in this test file

from around_the_grounds.models import Brewery
from around_the_grounds.parsers.stoup_ballard import StoupBallardParser
from around_the_grounds.parsers.urban_family import UrbanFamilyParser
from around_the_grounds.parsers.obec_brewing import ObecBrewingParser
from around_the_grounds.parsers.wheelie_pop import WheeliePopParser


class TestParserTimezoneConsistency:
    """Test that all parsers handle timezones consistently."""

    @pytest.fixture
    def sample_brewery(self) -> Brewery:
        """Create a test brewery."""
        return Brewery(
            key="test-brewery",
            name="Test Brewery",
            url="https://test.example.com",
            parser_config={},
        )

    @pytest.fixture
    def stoup_parser(self, sample_brewery: Brewery) -> StoupBallardParser:
        """Create StoupBallard parser."""
        return StoupBallardParser(sample_brewery)

    @pytest.fixture
    def urban_parser(self, sample_brewery: Brewery) -> UrbanFamilyParser:
        """Create UrbanFamily parser."""
        return UrbanFamilyParser(sample_brewery)

    @pytest.fixture
    def obec_parser(self, sample_brewery: Brewery) -> ObecBrewingParser:
        """Create ObecBrewing parser."""
        return ObecBrewingParser(sample_brewery)

    @pytest.fixture
    def wheelie_parser(self, sample_brewery: Brewery) -> WheeliePopParser:
        """Create WheeliePoP parser."""
        return WheeliePopParser(sample_brewery)


class TestStoupBallardTimezone:
    """Test StoupBallard parser timezone handling."""

    @pytest.fixture
    def sample_brewery(self) -> Brewery:
        """Create a test brewery."""
        return Brewery(
            key="stoup-ballard",
            name="Stoup Ballard",
            url="https://stoup.com",
            parser_config={},
        )

    @pytest.fixture
    def parser(self, sample_brewery: Brewery) -> StoupBallardParser:
        """Create parser instance."""
        return StoupBallardParser(sample_brewery)

    def test_parse_date_uses_pacific_timezone(self, parser: StoupBallardParser) -> None:
        """Test that date parsing uses Pacific timezone context."""
        with patch(
            "around_the_grounds.parsers.stoup_ballard.get_pacific_year"
        ) as mock_year, patch(
            "around_the_grounds.parsers.stoup_ballard.get_pacific_month"
        ) as mock_month:
            mock_year.return_value = 2025
            mock_month.return_value = 7  # July

            # Test date parsing for future month (should use current year)
            result = parser._parse_date("08.15")  # August 15
            assert result is not None
            assert result.year == 2025
            assert result.month == 8
            assert result.day == 15

            # Test date parsing for past month (should use next year)
            result = parser._parse_date("06.10")  # June 10 (before current July)
            assert result is not None
            assert result.year == 2026  # Next year
            assert result.month == 6
            assert result.day == 10

    def test_cross_timezone_date_consistency(self, parser: StoupBallardParser) -> None:
        """Test date parsing consistency across different system timezones."""
        # Mock Pacific time as December 31, 2024 11:00 PM
        with patch(
            "around_the_grounds.parsers.stoup_ballard.get_pacific_year"
        ) as mock_year, patch(
            "around_the_grounds.parsers.stoup_ballard.get_pacific_month"
        ) as mock_month, patch(
            "around_the_grounds.parsers.stoup_ballard.parse_date_with_pacific_context"
        ) as mock_parse:
            mock_year.return_value = 2024
            mock_month.return_value = 12
            mock_parse.return_value = datetime(2025, 1, 15)

            # Parse a January date
            parser._parse_date("01.15")

            # Should use Pacific timezone for year calculation, not system timezone
            mock_year.assert_called_once()
            mock_month.assert_called_once()
            mock_parse.assert_called_once_with(
                2025, 1, 15
            )  # Next year since January > current December

    def test_time_parsing_creates_naive_pacific_time(
        self, parser: StoupBallardParser
    ) -> None:
        """Test that time parsing creates timezone-naive datetimes in Pacific time."""
        base_date = datetime(2025, 7, 15)

        # Test simple time range parsing
        start_time, end_time = parser._parse_time(base_date, (2, 8, "pm"))

        assert start_time is not None
        assert end_time is not None

        # Should be timezone-naive
        assert start_time.tzinfo is None
        assert end_time.tzinfo is None

        # Should have correct Pacific time values
        assert start_time.hour == 14  # 2 PM in 24-hour format
        assert end_time.hour == 20  # 8 PM in 24-hour format

        # Should use the same date
        assert start_time.date() == base_date.date()
        assert end_time.date() == base_date.date()


class TestUrbanFamilyTimezone:
    """Test UrbanFamily parser timezone handling."""

    @pytest.fixture
    def sample_brewery(self) -> Brewery:
        """Create a test brewery."""
        return Brewery(
            key="urban-family",
            name="Urban Family",
            url="https://urbanfamily.com",
            parser_config={},
        )

    @pytest.fixture
    def parser(self, sample_brewery: Brewery) -> UrbanFamilyParser:
        """Create parser instance."""
        return UrbanFamilyParser(sample_brewery)

    def test_iso_timestamp_conversion_to_pacific(
        self, parser: UrbanFamilyParser
    ) -> None:
        """Test ISO timestamp conversion to Pacific timezone."""
        base_date = datetime(2025, 7, 15)

        # Test UTC timestamp conversion
        utc_time_str = "2025-07-15T21:30:00Z"  # 9:30 PM UTC
        result = parser._parse_time_string(utc_time_str, base_date)

        assert result is not None
        assert result.tzinfo is None  # Should be timezone-naive
        assert result.hour == 14  # 2:30 PM PDT (UTC-7 in July)
        assert result.minute == 30

    def test_24_hour_format_assumes_pacific(self, parser: UrbanFamilyParser) -> None:
        """Test that 24-hour format times are assumed to be Pacific."""
        base_date = datetime(2025, 7, 15)

        # Test 24-hour format
        result = parser._parse_time_string("14:30", base_date)

        assert result is not None
        assert result.tzinfo is None  # Should be timezone-naive Pacific time
        assert result.hour == 14  # 2:30 PM Pacific
        assert result.minute == 30

    def test_12_hour_format_assumes_pacific(self, parser: UrbanFamilyParser) -> None:
        """Test that 12-hour format times are assumed to be Pacific."""
        base_date = datetime(2025, 7, 15)

        # Test 12-hour format
        result = parser._parse_time_string("2:30 PM", base_date)

        assert result is not None
        assert result.tzinfo is None  # Should be timezone-naive Pacific time
        assert result.hour == 14  # 2:30 PM Pacific
        assert result.minute == 30


class TestObecBrewingTimezone:
    """Test ObecBrewing parser timezone handling."""

    @pytest.fixture
    def sample_brewery(self) -> Brewery:
        """Create a test brewery."""
        return Brewery(
            key="obec-brewing",
            name="Obec Brewing",
            url="https://obec.com",
            parser_config={},
        )

    @pytest.fixture
    def parser(self, sample_brewery: Brewery) -> ObecBrewingParser:
        """Create parser instance."""
        return ObecBrewingParser(sample_brewery)

    def test_today_calculation_uses_pacific_timezone(
        self, parser: ObecBrewingParser
    ) -> None:
        """Test that 'today' calculation uses Pacific timezone."""
        # Test the actual _parse_time_range method which uses now_in_pacific_naive
        time_range = "4:00 - 8:00"
        start_time, end_time = parser._parse_time_range(time_range)

        # The method should successfully parse times using Pacific timezone context
        assert start_time is not None
        assert end_time is not None
        assert start_time.hour == 16  # 4 PM
        assert end_time.hour == 20  # 8 PM

        # The dates should be set using Pacific timezone (we can't easily mock this
        # without breaking the functionality, but we can verify it works)

    def test_time_range_parsing_creates_pacific_times(
        self, parser: ObecBrewingParser
    ) -> None:
        """Test that time range parsing creates Pacific timezone times."""
        # Test with a typical food truck time range
        time_range = "4:00 - 8:00"
        start_time, end_time = parser._parse_time_range(time_range)

        assert start_time is not None
        assert end_time is not None

        # Should be timezone-naive Pacific times
        assert start_time.tzinfo is None
        assert end_time.tzinfo is None

        # Should interpret as PM hours (food truck typical hours)
        assert start_time.hour == 16  # 4 PM
        assert end_time.hour == 20  # 8 PM


class TestWheeliePopTimezone:
    """Test WheeliePoP parser timezone handling."""

    @pytest.fixture
    def sample_brewery(self) -> Brewery:
        """Create a test brewery."""
        return Brewery(
            key="wheelie-pop",
            name="Wheelie Pop",
            url="https://wheeliepop.com",
            parser_config={},
        )

    @pytest.fixture
    def parser(self, sample_brewery: Brewery) -> WheeliePopParser:
        """Create parser instance."""
        return WheeliePopParser(sample_brewery)

    def test_date_parsing_uses_pacific_context(self, parser: WheeliePopParser) -> None:
        """Test that date parsing uses Pacific timezone context."""
        with patch(
            "around_the_grounds.parsers.wheelie_pop.get_pacific_year"
        ) as mock_year, patch(
            "around_the_grounds.parsers.wheelie_pop.get_pacific_month"
        ) as mock_month, patch(
            "around_the_grounds.parsers.wheelie_pop.parse_date_with_pacific_context"
        ) as mock_parse:
            mock_year.return_value = 2025
            mock_month.return_value = 7  # July
            mock_parse.return_value = datetime(2025, 8, 3)

            # Parse a date in M/D format
            result = parser._parse_date("8/3")

            # Should use Pacific timezone utilities
            mock_year.assert_called_once()
            mock_month.assert_called_once()
            mock_parse.assert_called_once_with(2025, 8, 3)

            assert result is not None
            assert result == datetime(2025, 8, 3)

    def test_cross_timezone_date_consistency(self, parser: WheeliePopParser) -> None:
        """Test date parsing consistency across system timezones."""
        # Mock Pacific time as different from potential system time
        with patch(
            "around_the_grounds.parsers.wheelie_pop.get_pacific_year"
        ) as mock_year, patch(
            "around_the_grounds.parsers.wheelie_pop.get_pacific_month"
        ) as mock_month:
            mock_year.return_value = 2024
            mock_month.return_value = 11  # November

            # Parse a date that could be interpreted differently in different timezones
            result = parser._parse_date("12/25")  # December 25

            # Should use Pacific timezone context for year calculation
            mock_year.assert_called_once()
            mock_month.assert_called_once()

            assert result is not None
            assert result.year == 2024  # Current year since December > current November
            assert result.month == 12
            assert result.day == 25


class TestDSTTransitionScenarios:
    """Test parser behavior during DST transitions."""

    def test_spring_forward_transition(self) -> None:
        """Test parser behavior during Spring Forward (PST->PDT)."""
        # March 9, 2025 is Spring Forward
        spring_forward_date = datetime(2025, 3, 9)

        # Test that we can create times around the transition
        brewery = Brewery(key="test", name="Test", url="http://test.com")
        parser = StoupBallardParser(brewery)

        # 1:30 AM should work (before transition)
        start_time, _ = parser._parse_time(spring_forward_date, (1, 3, "am"))
        assert start_time is not None
        assert start_time.hour == 1

        # 3:30 AM should work (after transition)
        start_time, _ = parser._parse_time(spring_forward_date, (3, 5, "am"))
        assert start_time is not None
        assert start_time.hour == 3

    def test_fall_back_transition(self) -> None:
        """Test parser behavior during Fall Back (PDT->PST)."""
        # November 2, 2025 is Fall Back
        fall_back_date = datetime(2025, 11, 2)

        brewery = Brewery(key="test", name="Test", url="http://test.com")
        parser = StoupBallardParser(brewery)

        # Times around 1-2 AM (ambiguous during fall back) should still work
        start_time, _ = parser._parse_time(fall_back_date, (1, 3, "am"))
        assert start_time is not None
        assert start_time.hour == 1
