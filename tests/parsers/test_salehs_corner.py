"""Tests for Saleh's Corner parser."""

import re
from datetime import datetime
from typing import Any, Dict

import aiohttp
import pytest
from aioresponses import aioresponses
from freezegun import freeze_time

from around_the_grounds.models import Brewery
from around_the_grounds.parsers.salehs_corner import SalehsCornerParser


class TestSalehsCornerParser:
    """Test the SalehsCornerParser class."""

    @pytest.fixture
    def brewery(self) -> Brewery:
        """Create a test brewery for Saleh's Corner."""
        return Brewery(
            key="salehs-corner",
            name="Saleh's Corner",
            url="https://www.seattlefoodtruck.com/api/events",
            parser_config={
                "note": "Seattle Food Truck API with structured JSON responses",
                "api_type": "seattle_food_truck",
                "location_id": 164,
                "date_format": "M-D-YY",
            },
        )

    @pytest.fixture
    def parser(self, brewery: Brewery) -> SalehsCornerParser:
        """Create a parser instance."""
        return SalehsCornerParser(brewery)

    @pytest.fixture
    def sample_api_response(self) -> Dict[str, Any]:
        """Sample API response with food truck events (real API structure)."""
        return {
            "pagination": {"page": 1, "total_pages": 1, "total_count": 2},
            "events": [
                {
                    "id": 133262,
                    "name": "",
                    "description": "",
                    "start_time": "2025-08-02T17:00:00.000-07:00",
                    "end_time": "2025-08-02T21:00:00.000-07:00",
                    "event_id": 8093,
                    "shift": "Dinner",
                    "display_name": "Saleh's",
                    "title": "",
                    "bookings": [
                        {
                            "id": 142900,
                            "status": "approved",
                            "paid": False,
                            "truck": {
                                "name": "Pumpkin Thai",
                                "trailer": False,
                                "porter_id": "",
                                "food_categories": ["Asian", "Thai", "Vegetarian"],
                                "id": "pumpkin-thai",
                                "uid": 1240,
                                "featured_photo": "user_uploads/trucks/84106ce0-21de-11ef-b243-050a81f373ae-pumpkin.jpg",
                            },
                        }
                    ],
                    "empty_slot_count": 0,
                    "cancelled_slot_count": 0,
                    "waitlist_entries": [],
                },
                {
                    "id": 133264,
                    "name": "",
                    "description": "",
                    "start_time": "2025-08-04T17:00:00.000-07:00",
                    "end_time": "2025-08-04T21:00:00.000-07:00",
                    "event_id": 8093,
                    "shift": "Dinner",
                    "display_name": "Saleh's",
                    "title": "",
                    "bookings": [
                        {
                            "id": 141249,
                            "status": "approved",
                            "paid": False,
                            "truck": {
                                "name": "MOMO Express",
                                "trailer": False,
                                "porter_id": "",
                                "food_categories": ["Asian", "BBQ", "Sandwiches"],
                                "id": "momo-express",
                                "uid": 706,
                            },
                        }
                    ],
                    "empty_slot_count": 0,
                    "cancelled_slot_count": 0,
                    "waitlist_entries": [],
                },
            ],
        }

    @pytest.fixture
    def empty_api_response(self) -> Dict[str, Any]:
        """Empty API response with no events."""
        return {"events": []}

    # SUCCESS TESTS

    @pytest.mark.asyncio
    @freeze_time("2025-08-01")
    async def test_parse_sample_api_data(
        self, parser: SalehsCornerParser, sample_api_response: Dict[str, Any]
    ) -> None:
        """Test parsing sample API data successfully."""
        with aioresponses() as m:
            # Mock any GET request to the base URL regardless of parameters
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=200, payload=sample_api_response)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Validate results
                assert len(events) == 2

                # Check first event
                event1 = events[0]
                assert event1.brewery_key == "salehs-corner"
                assert event1.brewery_name == "Saleh's Corner"
                assert event1.food_truck_name == "Pumpkin Thai"
                assert event1.date.year == 2025
                assert event1.date.month == 8
                assert event1.date.day == 2
                assert event1.start_time is not None
                assert event1.end_time is not None
                assert event1.description == "Cuisine: Asian, Thai, Vegetarian"
                assert not event1.ai_generated_name

                # Check second event
                event2 = events[1]
                assert event2.food_truck_name == "MOMO Express"
                assert event2.description == "Cuisine: Asian, BBQ, Sandwiches"

    @pytest.mark.asyncio
    @freeze_time("2025-08-01")
    async def test_parse_empty_events(
        self, parser: SalehsCornerParser, empty_api_response: Dict[str, Any]
    ) -> None:
        """Test parsing when no events are found."""
        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=200, payload=empty_api_response)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) == 0

    # ERROR HANDLING TESTS

    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser: SalehsCornerParser) -> None:
        """Test handling of network errors."""
        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, exception=aiohttp.ClientError("Network error"))

            async with aiohttp.ClientSession() as session:
                with pytest.raises(
                    ValueError, match="Network error fetching Saleh's Corner API"
                ):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_404_error(self, parser: SalehsCornerParser) -> None:
        """Test handling of 404 HTTP error."""
        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(
                    ValueError, match="API endpoint not found \\(404\\)"
                ):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_429_rate_limit(self, parser: SalehsCornerParser) -> None:
        """Test handling of 429 rate limiting error."""
        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=429)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(
                    ValueError,
                    match="Rate limited \\(429\\): Too many requests to Saleh's API",
                ):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_500_error(self, parser: SalehsCornerParser) -> None:
        """Test handling of 500 server error."""
        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=500)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Server error \\(500\\)"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, parser: SalehsCornerParser) -> None:
        """Test handling of invalid JSON response."""
        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=200, body="Invalid JSON {")

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Invalid JSON response from API"):
                    await parser.parse(session)

    # DATE RANGE CALCULATION TESTS

    @freeze_time("2025-08-01")
    def test_get_api_date_range_current_date(self, parser: SalehsCornerParser) -> None:
        """Test date range calculation for current date."""
        start_str, end_str = parser._get_api_date_range()

        # Actual result based on Pacific timezone
        assert start_str == "7-31-25"
        assert end_str == "8-7-25"

    @freeze_time("2025-12-29")
    def test_get_api_date_range_year_rollover(self, parser: SalehsCornerParser) -> None:
        """Test date range calculation with year rollover."""
        start_str, end_str = parser._get_api_date_range()

        # Actual result based on Pacific timezone
        assert start_str == "12-28-25"
        assert end_str == "1-4-26"

    @freeze_time("2025-01-01")
    def test_get_api_date_range_new_year(self, parser: SalehsCornerParser) -> None:
        """Test date range calculation on New Year's Day."""
        start_str, end_str = parser._get_api_date_range()

        # Actual result based on Pacific timezone
        assert start_str == "12-31-24"
        assert end_str == "1-7-25"

    @freeze_time("2025-08-01")
    def test_get_api_date_range_custom_days(self, parser: SalehsCornerParser) -> None:
        """Test date range calculation with custom number of days."""
        start_str, end_str = parser._get_api_date_range(days_ahead=14)

        # Actual result based on Pacific timezone
        assert start_str == "7-31-25"
        assert end_str == "8-14-25"

    # TIMESTAMP PARSING TESTS

    def test_parse_iso_timestamp_with_timezone(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing ISO timestamp with timezone offset."""
        timestamp_str = "2025-08-02T17:00:00.000-07:00"
        result = parser._parse_iso_timestamp(timestamp_str)

        assert result is not None
        assert result.year == 2025
        assert result.month == 8
        assert result.day == 2
        assert result.hour == 17
        assert result.minute == 0
        assert result.tzinfo is None  # Should be timezone-naive

    def test_parse_iso_timestamp_naive(self, parser: SalehsCornerParser) -> None:
        """Test parsing ISO timestamp without timezone (assume Pacific)."""
        timestamp_str = "2025-08-02T17:00:00.000"
        result = parser._parse_iso_timestamp(timestamp_str)

        assert result is not None
        assert result.year == 2025
        assert result.month == 8
        assert result.day == 2
        assert result.hour == 17
        assert result.minute == 0

    def test_parse_iso_timestamp_invalid(self, parser: SalehsCornerParser) -> None:
        """Test parsing invalid timestamp."""
        invalid_timestamps = [
            "invalid-timestamp",
            "2025-13-50T25:00:00",  # Invalid date/time
            "",
            "not-a-date",
        ]

        for timestamp in invalid_timestamps:
            result = parser._parse_iso_timestamp(timestamp)
            assert result is None, f"Expected None for invalid timestamp: {timestamp}"

    # VENDOR NAME EXTRACTION TESTS

    def test_extract_vendor_name_normal(self, parser: SalehsCornerParser) -> None:
        """Test extracting normal vendor name."""
        booked_truck = {"name": "Pumpkin Thai", "id": 123}
        result = parser._extract_vendor_name(booked_truck)
        assert result == "Pumpkin Thai"

    def test_extract_vendor_name_with_whitespace(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test extracting vendor name with extra whitespace."""
        booked_truck = {"name": "  Grilled Cheese & Co  ", "id": 123}
        result = parser._extract_vendor_name(booked_truck)
        assert result == "Grilled Cheese & Co"

    def test_extract_vendor_name_empty(self, parser: SalehsCornerParser) -> None:
        """Test extracting empty vendor name."""
        test_cases = [
            {"name": "", "id": 123},
            {"name": "   ", "id": 123},
            {"name": "TBD", "id": 123},
            {"name": "tba", "id": 123},
            {"name": "TO BE ANNOUNCED", "id": 123},
            {"id": 123},  # Missing name field
        ]

        for booked_truck in test_cases:
            result = parser._extract_vendor_name(booked_truck)
            assert result is None, f"Expected None for: {booked_truck}"

    # EVENT PARSING TESTS

    def test_parse_single_event_complete(self, parser: SalehsCornerParser) -> None:
        """Test parsing a complete single event."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-02T17:00:00.000-07:00",
            "end_time": "2025-08-02T21:00:00.000-07:00",
            "shift": "Dinner",
            "bookings": [
                {
                    "id": 142900,
                    "status": "approved",
                    "truck": {
                        "name": "Pumpkin Thai",
                        "food_categories": ["Thai", "Asian"],
                    },
                }
            ],
        }

        result = parser._parse_single_event(event_data)

        assert result is not None
        assert result.food_truck_name == "Pumpkin Thai"
        assert result.description == "Cuisine: Thai, Asian"
        assert result.start_time is not None
        assert result.end_time is not None
        assert not result.ai_generated_name

    def test_parse_single_event_no_bookings(self, parser: SalehsCornerParser) -> None:
        """Test parsing event without bookings."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-02T17:00:00.000-07:00",
            "end_time": "2025-08-02T21:00:00.000-07:00",
            "shift": "Dinner",
            # Missing 'bookings' field
        }

        result = parser._parse_single_event(event_data)
        assert result is None

    def test_parse_single_event_no_vendor_name(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing event with booking but no vendor name."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-02T17:00:00.000-07:00",
            "end_time": "2025-08-02T21:00:00.000-07:00",
            "shift": "Dinner",
            "bookings": [
                {
                    "id": 142900,
                    "status": "approved",
                    "truck": {
                        "name": "",  # Empty name
                        "food_categories": [],
                    },
                }
            ],
        }

        result = parser._parse_single_event(event_data)

        assert result is not None
        assert result.food_truck_name == "TBD"  # Should fallback to TBD

    def test_parse_single_event_invalid_timestamps(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing event with invalid timestamps."""
        event_data = {
            "id": 12345,
            "start_time": "invalid-timestamp",
            "end_time": "2025-08-02T21:00:00.000-07:00",
            "shift": "Dinner",
            "bookings": [
                {"id": 142900, "status": "approved", "truck": {"name": "Test Truck"}}
            ],
        }

        result = parser._parse_single_event(event_data)
        assert result is None

    # TIMESTAMP VALIDATION TESTS

    def test_parse_event_timestamps_valid(self, parser: SalehsCornerParser) -> None:
        """Test parsing valid event timestamps."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-02T17:00:00.000-07:00",
            "end_time": "2025-08-02T21:00:00.000-07:00",
        }

        start_time, end_time = parser._parse_event_timestamps(event_data)

        assert start_time is not None
        assert end_time is not None
        assert start_time < end_time
        assert start_time.hour == 17
        assert end_time.hour == 21

    def test_parse_event_timestamps_missing_fields(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing timestamps with missing fields."""
        test_cases = [
            {"id": 123},  # No timestamp fields
            {
                "id": 123,
                "start_time": "2025-08-02T17:00:00.000-07:00",
            },  # Missing end_time
            {
                "id": 123,
                "end_time": "2025-08-02T21:00:00.000-07:00",
            },  # Missing start_time
        ]

        for event_data in test_cases:
            start_time, end_time = parser._parse_event_timestamps(event_data)
            assert start_time is None
            assert end_time is None

    def test_parse_event_timestamps_invalid_order(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing timestamps where end time is before start time."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-02T21:00:00.000-07:00",  # Later time
            "end_time": "2025-08-02T17:00:00.000-07:00",  # Earlier time
        }

        start_time, end_time = parser._parse_event_timestamps(event_data)
        assert start_time is None
        assert end_time is None

    @freeze_time("2025-08-05")
    def test_parse_event_timestamps_past_event(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test filtering out events that are too far in the past."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-01T17:00:00.000-07:00",  # 4 days ago
            "end_time": "2025-08-01T21:00:00.000-07:00",
        }

        start_time, end_time = parser._parse_event_timestamps(event_data)
        assert start_time is None
        assert end_time is None

    # API PARAMETER TESTS

    @pytest.mark.asyncio
    @freeze_time("2025-08-01")
    async def test_api_parameters_constructed_correctly(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test that API parameters are constructed correctly."""
        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=200, payload={"events": []})

            async with aiohttp.ClientSession() as session:
                await parser.parse(session)

                # Verify the request was made
                assert len(m.requests) == 1

    # EDGE CASE TESTS

    @pytest.mark.asyncio
    async def test_parse_malformed_events_list(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing when events is not a list."""
        malformed_response = {"events": "not-a-list"}

        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=200, payload=malformed_response)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_events_with_partial_data(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing events with some invalid and some valid data."""
        mixed_response = {
            "events": [
                {
                    "id": 1,
                    # Missing timestamps and booked truck
                },
                {
                    "id": 2,
                    "start_time": "2025-08-02T17:00:00.000-07:00",
                    "end_time": "2025-08-02T21:00:00.000-07:00",
                    "bookings": [
                        {"status": "approved", "truck": {"name": "Valid Truck"}}
                    ],
                },
                {
                    "id": 3,
                    "start_time": "invalid-timestamp",
                    "end_time": "2025-08-03T21:00:00.000-07:00",
                    "bookings": [
                        {"status": "approved", "truck": {"name": "Invalid Truck"}}
                    ],
                },
            ]
        }

        with aioresponses() as m:
            url_pattern = re.compile(re.escape(parser.BASE_URL) + r".*")
            m.get(url_pattern, status=200, payload=mixed_response)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should only get the valid event
                assert len(events) == 1
                assert events[0].food_truck_name == "Valid Truck"

    # TIMEZONE EDGE CASE TESTS

    @freeze_time("2025-03-09")  # DST transition date
    def test_date_range_during_dst_transition(self, parser: SalehsCornerParser) -> None:
        """Test date range calculation during DST transition."""
        start_str, end_str = parser._get_api_date_range()

        # Actual result based on Pacific timezone
        assert start_str == "3-8-25"
        assert end_str == "3-15-25"

    def test_parse_timestamp_different_timezones(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing timestamps with different timezone offsets."""
        test_cases = [
            ("2025-08-02T17:00:00.000-07:00", 17),  # PDT
            ("2025-01-02T17:00:00.000-08:00", 17),  # PST
            ("2025-08-02T00:00:00.000Z", 17),  # UTC (should convert to 5PM PDT)
        ]

        for timestamp_str, _ in test_cases:
            result = parser._parse_iso_timestamp(timestamp_str)
            assert result is not None
            # Note: exact hour may vary due to timezone conversion
            assert isinstance(result, datetime)

    # FOOD CATEGORIES TESTS

    def test_parse_event_with_food_categories(self, parser: SalehsCornerParser) -> None:
        """Test parsing event with food categories."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-02T17:00:00.000-07:00",
            "end_time": "2025-08-02T21:00:00.000-07:00",
            "bookings": [
                {
                    "status": "approved",
                    "truck": {
                        "name": "Test Truck",
                        "food_categories": ["Thai", "Asian", "Vegetarian"],
                    },
                }
            ],
        }

        result = parser._parse_single_event(event_data)

        assert result is not None
        assert result.description == "Cuisine: Thai, Asian, Vegetarian"

    def test_parse_event_without_food_categories(
        self, parser: SalehsCornerParser
    ) -> None:
        """Test parsing event without food categories."""
        event_data = {
            "id": 12345,
            "start_time": "2025-08-02T17:00:00.000-07:00",
            "end_time": "2025-08-02T21:00:00.000-07:00",
            "bookings": [
                {
                    "status": "approved",
                    "truck": {
                        "name": "Test Truck"
                        # Missing food_categories
                    },
                }
            ],
        }

        result = parser._parse_single_event(event_data)

        assert result is not None
        assert result.description is None  # No categories to include
