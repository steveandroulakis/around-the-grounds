"""Tests for Urban Family parser."""

from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from around_the_grounds.models import Brewery
from around_the_grounds.parsers.urban_family import UrbanFamilyParser


class TestUrbanFamilyParser:
    """Test the UrbanFamilyParser class."""

    @pytest.fixture
    def brewery(self) -> Brewery:
        """Create a test brewery for Urban Family."""
        return Brewery(
            key="urban-family",
            name="Urban Family Brewing",
            url="https://app.hivey.io/urbanfamily/public-calendar",
            parser_config={
                "api_endpoint": "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar",
                "api_type": "hivey_calendar",
            },
        )

    @pytest.fixture
    def parser(self, brewery: Brewery) -> UrbanFamilyParser:
        """Create a parser instance."""
        return UrbanFamilyParser(brewery)

    @pytest.fixture
    def wordpress_brewery(self) -> Brewery:
        """Create a test brewery using WordPress Sugar Calendar source."""
        return Brewery(
            key="urban-family",
            name="Urban Family Brewing",
            url="https://urbanfamilybrewing.com/home/calendar/",
            parser_config={
                "calendar_url": "https://urbanfamilybrewing.com/home/calendar/",
                "calendar_ajax_endpoint": "https://urbanfamilybrewing.com/wp-admin/admin-ajax.php",
                "api_endpoint": "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar",
            },
        )

    @pytest.fixture
    def wordpress_parser(self, wordpress_brewery: Brewery) -> UrbanFamilyParser:
        """Create a parser instance configured for WordPress source."""
        return UrbanFamilyParser(wordpress_brewery)

    @pytest.fixture
    def sugar_calendar_html(self) -> str:
        """Minimal Sugar Calendar month-view HTML fixture."""
        return """
        <html>
            <body>
                <div id="sc-code-1"
                     class="sugar-calendar-block sugar-calendar-block__month-view"
                     data-attributes='{"display":"month"}'
                     data-accentcolor="#5685BD"
                     data-ogday="3"
                     data-ogmonth="3"
                     data-ogyear="2026">
                    <form class="sugar-calendar-block-settings">
                        <input type="hidden" name="sc_calendar_id" value="sc-code-1" />
                        <input type="hidden" name="sc_month" value="3" />
                        <input type="hidden" name="sc_year" value="2026" />
                        <input type="hidden" name="sc_day" value="3" />
                        <input type="hidden" name="sc_display" value="month" />
                    </form>

                    <div data-eventurl="https://urbanfamilybrewing.com/events/9th-and-hennepin/"
                         data-calendarsinfo='{"calendars":[{"name":"Food Truck Calendar","color":"#57d466"},{"name":"Urban Family Brewing Ballard","color":"#5685BD"}],"primary_event_color":"#57d466"}'
                         class="sugar-calendar-block__event-cell">
                        <div class="sugar-calendar-block__event-cell__time">
                            <time datetime="2026-03-01T08:00:00">8:00 am</time> -
                            <time datetime="2026-03-01T12:00:00">12:00 pm</time>
                        </div>
                        <div class="sugar-calendar-block__event-cell__title">9th and Hennepin</div>
                    </div>

                    <div data-eventurl="https://urbanfamilybrewing.com/events/trivia-night/"
                         data-calendarsinfo='{"calendars":[{"name":"Urban Family Brewing Ballard","color":"#5685BD"}],"primary_event_color":"#5685BD"}'
                         class="sugar-calendar-block__event-cell">
                        <div class="sugar-calendar-block__event-cell__time">
                            <time datetime="2026-03-01T19:30:00">7:30 pm</time> -
                            <time datetime="2026-03-01T21:30:00">9:30 pm</time>
                        </div>
                        <div class="sugar-calendar-block__event-cell__title">First Tuesday Trivia</div>
                    </div>
                </div>

                <script>
                    var sugar_calendar_obj = {"ajax_url":"https://urbanfamilybrewing.com/wp-admin/admin-ajax.php","nonce":"908125549b"};
                </script>
            </body>
        </html>
        """

    @pytest.fixture
    def sugar_calendar_next_month_payload(self) -> Dict[str, Any]:
        """AJAX payload containing next-month Sugar Calendar HTML body."""
        return {
            "success": True,
            "data": {
                "body": """
                    <div data-eventurl="https://urbanfamilybrewing.com/events/kaosamai/"
                         data-calendarsinfo='{"calendars":[{"name":"Food Truck Calendar","color":"#57d466"}],"primary_event_color":"#57d466"}'
                         class="sugar-calendar-block__event-cell">
                        <div class="sugar-calendar-block__event-cell__time">
                            <time datetime="2026-04-01T13:00:00">1:00 pm</time> -
                            <time datetime="2026-04-01T19:00:00">7:00 pm</time>
                        </div>
                        <div class="sugar-calendar-block__event-cell__title">Kaosamai</div>
                    </div>
                """
            },
        }

    @pytest.fixture
    def sample_api_response(self) -> List[Dict[str, Any]]:
        """Sample API response with food truck events."""
        return [
            {
                "_id": {"$oid": "67f70d76e4ca31e444ef63eb"},
                "applicantVendors": [
                    {
                        "applicationType": "manuallyAdded",
                        "status": "confirmed",
                        "vendorId": "67f6f627e4ca31e444ef637e",
                    }
                ],
                "associatedVenue": {"$oid": "67edae71e9f3be17e2ef6380"},
                "eventDates": [
                    {"date": "July 06, 2025", "endTime": "19:00", "startTime": "13:00"}
                ],
                "eventDescription": "",
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/kaosamia.png",
                "eventStatus": "upcoming",
                "eventTitle": "FOOD TRUCK - Kaosamia Thai",
                "isApplicationOpen": True,
                "isPublished": True,
                "location": "Urban Family Brewing (1103 NW 52nd st, seattle, Washington)",
            },
            {
                "_id": {"$oid": "67f703a7e4ca31e444ef6394"},
                "applicantVendors": [
                    {
                        "applicationType": "manuallyAdded",
                        "status": "confirmed",
                        "vendorId": "67f6f44de4ca31e444ef637d",
                    }
                ],
                "associatedVenue": {"$oid": "67edae71e9f3be17e2ef6380"},
                "eventDates": [
                    {"date": "July 07, 2025", "endTime": "20:00", "startTime": "16:00"}
                ],
                "eventDescription": "",
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/UpdatedLogo_BLK.png",
                "eventStatus": "upcoming",
                "eventTitle": "FOOD TRUCK",
                "isApplicationOpen": True,
                "isPublished": True,
                "location": "Urban Family Brewing (1103 NW 52nd st, seattle, Washington)",
            },
        ]

    @pytest.fixture
    def sample_api_response_with_image_names(self) -> List[Dict[str, Any]]:
        """API response where food truck names need to be extracted from image URLs."""
        return [
            {
                "_id": {"$oid": "test1"},
                "applicantVendors": [{"status": "confirmed"}],
                "eventDates": [
                    {"date": "July 08, 2025", "startTime": "16:00", "endTime": "20:00"}
                ],
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/georgia_greek_logo.jpg",
                "eventTitle": "FOOD TRUCK",
                "eventStatus": "upcoming",
            },
            {
                "_id": {"$oid": "test2"},
                "applicantVendors": [{"status": "confirmed"}],
                "eventDates": [
                    {"date": "July 09, 2025", "startTime": "13:00", "endTime": "19:00"}
                ],
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/woodshop_bbq.png",
                "eventTitle": "FOOD TRUCK",
                "eventStatus": "upcoming",
            },
        ]

    @pytest.mark.asyncio
    @patch(
        "around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image"
    )
    async def test_parse_success_with_api_data(
        self,
        mock_vision: Mock,
        parser: UrbanFamilyParser,
        sample_api_response: List[Dict[str, Any]],
    ) -> None:
        """Test successful parsing of API data."""
        # Mock vision analysis to return None for the generic logo
        mock_vision.return_value = None

        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, status=200, payload=sample_api_response)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        assert len(events) == 2

        # Check first event (with explicit title)
        event1 = events[0]
        assert event1.brewery_key == "urban-family"
        assert event1.brewery_name == "Urban Family Brewing"
        assert event1.food_truck_name == "Kaosamia Thai"
        assert event1.date == datetime(2025, 7, 6)
        assert event1.start_time == datetime(2025, 7, 6, 13, 0)
        assert event1.end_time == datetime(2025, 7, 6, 19, 0)

        # Check second event (vendor ID mapping now provides correct name)
        event2 = events[1]
        assert event2.brewery_key == "urban-family"
        assert event2.brewery_name == "Urban Family Brewing"
        assert (
            event2.food_truck_name == "Tolu Modern Fijian Cuisine"
        )  # Mapped from vendor ID 67f6f44de4ca31e444ef637d (was incorrectly "Blk" from filename before)
        assert event2.date == datetime(2025, 7, 7)
        assert event2.start_time == datetime(2025, 7, 7, 16, 0)
        assert event2.end_time == datetime(2025, 7, 7, 20, 0)

    @pytest.mark.asyncio
    async def test_parse_with_image_name_extraction(
        self,
        parser: UrbanFamilyParser,
        sample_api_response_with_image_names: List[Dict[str, Any]],
    ) -> None:
        """Test food truck name extraction from image URLs."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, status=200, payload=sample_api_response_with_image_names)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        assert len(events) == 2

        # Check name extraction from image filenames (improved logic removes "Logo")
        assert events[0].food_truck_name == "Georgia Greek"
        assert events[1].food_truck_name == "Woodshop Bbq"

    @pytest.mark.asyncio
    async def test_parse_empty_response(self, parser: UrbanFamilyParser) -> None:
        """Test parsing empty API response."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, status=200, payload=[])

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_api_error_404(self, parser: UrbanFamilyParser) -> None:
        """Test handling of 404 error from API."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(
                    ValueError, match="API endpoint not found \\(404\\)"
                ):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_api_error_403(self, parser: UrbanFamilyParser) -> None:
        """Test handling of 403 error from API."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, status=403)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Access forbidden \\(403\\)"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_api_error_500(self, parser: UrbanFamilyParser) -> None:
        """Test handling of 500 error from API."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, status=500)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Server error \\(500\\)"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_invalid_json_response(self, parser: UrbanFamilyParser) -> None:
        """Test handling of invalid JSON response."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, status=200, body="invalid json")

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Invalid JSON response from API"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser: UrbanFamilyParser) -> None:
        """Test handling of network errors."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        with aioresponses() as m:
            m.get(api_url, exception=aiohttp.ClientError("Network error"))

            async with aiohttp.ClientSession() as session:
                with pytest.raises(
                    ValueError, match="Network error fetching Urban Family API"
                ):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_filters_invalid_events(
        self, parser: UrbanFamilyParser
    ) -> None:
        """Test that invalid events are filtered out."""
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )

        invalid_events = [
            {
                # Missing eventDates
                "_id": {"$oid": "invalid1"},
                "eventTitle": "FOOD TRUCK - Valid Name",
                "eventStatus": "upcoming",
            },
            {
                # Missing food truck name
                "_id": {"$oid": "invalid2"},
                "eventDates": [
                    {"date": "July 10, 2025", "startTime": "16:00", "endTime": "20:00"}
                ],
                "eventTitle": "FOOD TRUCK",
                "eventImage": "https://example.com/logo.png",
                "eventStatus": "upcoming",
            },
            {
                # Valid event
                "_id": {"$oid": "valid1"},
                "eventDates": [
                    {"date": "July 11, 2025", "startTime": "16:00", "endTime": "20:00"}
                ],
                "eventTitle": "FOOD TRUCK - Good Eats",
                "eventStatus": "upcoming",
            },
        ]

        with aioresponses() as m:
            m.get(api_url, status=200, payload=invalid_events)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        # Both events should be returned - one with valid name, one with TBD
        assert len(events) == 2

        # Find the events by date
        event_by_date = {event.date.day: event for event in events}

        # Event without valid name should get TBD
        assert event_by_date[10].food_truck_name == "TBD"
        assert event_by_date[10].date == datetime(2025, 7, 10)

        # Event with valid name should keep it
        assert event_by_date[11].food_truck_name == "Good Eats"
        assert event_by_date[11].date == datetime(2025, 7, 11)

    def test_extract_food_truck_name_from_title(
        self, parser: UrbanFamilyParser
    ) -> None:
        """Test food truck name extraction from event title."""
        # Test explicit name in title
        item1 = {"eventTitle": "FOOD TRUCK - Awesome Tacos"}
        result, ai_generated = parser._extract_food_truck_name(item1)
        assert result == "Awesome Tacos"
        assert not ai_generated

        # Test title that's not just "FOOD TRUCK"
        item2 = {"eventTitle": "Special Event - Pizza Night"}
        result, ai_generated = parser._extract_food_truck_name(item2)
        assert result == "Special Event - Pizza Night"
        assert not ai_generated

        # Test generic "FOOD TRUCK" title (should return None for this test)
        item3 = {"eventTitle": "FOOD TRUCK"}
        result, ai_generated = parser._extract_food_truck_name(item3)
        assert result is None
        assert not ai_generated

    def test_extract_food_truck_name_from_image_url(
        self, parser: UrbanFamilyParser
    ) -> None:
        """Test food truck name extraction from image URL."""
        item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/awesome_tacos_logo.jpg",
        }
        result, ai_generated = parser._extract_food_truck_name(item)
        assert result == "Awesome Tacos"  # Improved logic removes "Logo" suffix
        assert not ai_generated

    def test_extract_food_truck_name_no_valid_name(
        self, parser: UrbanFamilyParser
    ) -> None:
        """Test when no valid food truck name can be extracted."""
        item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/logo.png",
        }
        result, ai_generated = parser._extract_food_truck_name(item)
        assert result is None
        assert not ai_generated

    def test_parse_urban_family_date_formats(self, parser: UrbanFamilyParser) -> None:
        """Test parsing various date formats."""
        # Standard format
        assert parser._parse_urban_family_date("July 06, 2025") == datetime(2025, 7, 6)

        # Without comma
        assert parser._parse_urban_family_date("July 06 2025") == datetime(2025, 7, 6)

        # Different month
        assert parser._parse_urban_family_date("December 25, 2025") == datetime(
            2025, 12, 25
        )

        # Invalid format should return None
        assert parser._parse_urban_family_date("invalid date") is None

    def test_parse_time_string_24_hour_format(self, parser: UrbanFamilyParser) -> None:
        """Test parsing 24-hour time format."""
        test_date = datetime(2025, 7, 6)

        # Standard 24-hour format
        assert parser._parse_time_string("13:00", test_date) == datetime(
            2025, 7, 6, 13, 0
        )
        assert parser._parse_time_string("19:30", test_date) == datetime(
            2025, 7, 6, 19, 30
        )
        assert parser._parse_time_string("09:15", test_date) == datetime(
            2025, 7, 6, 9, 15
        )

        # Edge cases
        assert parser._parse_time_string("00:00", test_date) == datetime(
            2025, 7, 6, 0, 0
        )
        assert parser._parse_time_string("23:59", test_date) == datetime(
            2025, 7, 6, 23, 59
        )

    def test_parse_time_string_12_hour_format(self, parser: UrbanFamilyParser) -> None:
        """Test parsing 12-hour time format with AM/PM."""
        test_date = datetime(2025, 7, 6)

        # PM times
        assert parser._parse_time_string("1:00 pm", test_date) == datetime(
            2025, 7, 6, 13, 0
        )
        assert parser._parse_time_string("12:30 PM", test_date) == datetime(
            2025, 7, 6, 12, 30
        )

        # AM times
        assert parser._parse_time_string("8:00 am", test_date) == datetime(
            2025, 7, 6, 8, 0
        )
        assert parser._parse_time_string("12:00 AM", test_date) == datetime(
            2025, 7, 6, 0, 0
        )

    def test_parse_time_string_invalid_formats(self, parser: UrbanFamilyParser) -> None:
        """Test parsing invalid time formats."""
        test_date = datetime(2025, 7, 6)

        # Invalid times should return None
        assert parser._parse_time_string("25:00", test_date) is None
        assert parser._parse_time_string("12:70", test_date) is None
        assert parser._parse_time_string("invalid", test_date) is None
        assert parser._parse_time_string("", test_date) is None

    def test_extract_times_from_event_dates(self, parser: UrbanFamilyParser) -> None:
        """Test time extraction from eventDates structure."""
        test_date = datetime(2025, 7, 6)

        item = {
            "eventDates": [
                {"date": "July 06, 2025", "startTime": "13:00", "endTime": "19:00"}
            ]
        }

        start_time, end_time = parser._extract_times(item, test_date)
        assert start_time == datetime(2025, 7, 6, 13, 0)
        assert end_time == datetime(2025, 7, 6, 19, 0)

    def test_extract_times_missing_data(self, parser: UrbanFamilyParser) -> None:
        """Test time extraction when data is missing."""
        test_date = datetime(2025, 7, 6)

        # Missing eventDates
        item1: Dict[str, Any] = {}
        start_time, end_time = parser._extract_times(item1, test_date)
        assert start_time is None
        assert end_time is None

        # Empty eventDates
        item2: Dict[str, Any] = {"eventDates": []}
        start_time, end_time = parser._extract_times(item2, test_date)
        assert start_time is None
        assert end_time is None

        # Missing time fields
        item3 = {"eventDates": [{"date": "July 06, 2025"}]}
        start_time, end_time = parser._extract_times(item3, test_date)
        assert start_time is None
        assert end_time is None

    def test_parse_json_data_dict_format(self, parser: UrbanFamilyParser) -> None:
        """Test parsing JSON data in dict format with 'events' key."""
        data = {
            "events": [
                {
                    "eventTitle": "FOOD TRUCK - Test Truck",
                    "eventDates": [
                        {
                            "date": "July 06, 2025",
                            "startTime": "13:00",
                            "endTime": "19:00",
                        }
                    ],
                    "eventStatus": "upcoming",
                }
            ]
        }

        events = parser._parse_json_data(data)
        assert len(events) == 1
        assert events[0].food_truck_name == "Test Truck"

    def test_parse_json_data_invalid_structure(self, parser: UrbanFamilyParser) -> None:
        """Test parsing invalid JSON data structure."""
        # String data should be handled gracefully (returns empty list)
        events = parser._parse_json_data("invalid data")
        assert events == []

        # Number data should be handled gracefully (returns empty list)
        events = parser._parse_json_data(123)
        assert events == []

    @pytest.mark.asyncio
    async def test_parse_wordpress_sugar_calendar(
        self,
        wordpress_parser: UrbanFamilyParser,
        sugar_calendar_html: str,
        sugar_calendar_next_month_payload: Dict[str, Any],
    ) -> None:
        """Test parsing current and next month from WordPress Sugar Calendar."""
        calendar_url = "https://urbanfamilybrewing.com/home/calendar/"
        ajax_url = "https://urbanfamilybrewing.com/wp-admin/admin-ajax.php"

        with aioresponses() as m:
            m.get(calendar_url, status=200, body=sugar_calendar_html)
            m.post(ajax_url, status=200, payload=sugar_calendar_next_month_payload)

            async with aiohttp.ClientSession() as session:
                events = await wordpress_parser.parse(session)

        # Should include only food-truck calendar events
        assert len(events) == 2
        event_names = sorted(event.food_truck_name for event in events)
        assert event_names == ["9th and Hennepin", "Kaosamai"]

    @pytest.mark.asyncio
    async def test_wordpress_403_falls_back_to_legacy_api(
        self, wordpress_parser: UrbanFamilyParser
    ) -> None:
        """Test legacy API fallback when WordPress calendar blocks scraper access."""
        calendar_url = "https://urbanfamilybrewing.com/home/calendar/"
        api_url = (
            "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        )
        fallback_payload = [
            {
                "eventDates": [
                    {"date": "July 06, 2025", "endTime": "19:00", "startTime": "13:00"}
                ],
                "eventTitle": "FOOD TRUCK - Kaosamia Thai",
                "eventStatus": "upcoming",
            }
        ]

        with aioresponses() as m:
            m.get(calendar_url, status=403)
            m.get(api_url, status=200, payload=fallback_payload)

            async with aiohttp.ClientSession() as session:
                events = await wordpress_parser.parse(session)

        assert len(events) == 1
        assert events[0].food_truck_name == "Kaosamia Thai"
