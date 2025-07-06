"""Tests for Urban Family parser."""

import pytest
from datetime import datetime
import aiohttp
from aioresponses import aioresponses
import json

from around_the_grounds.parsers.urban_family import UrbanFamilyParser
from around_the_grounds.models import Brewery, FoodTruckEvent


class TestUrbanFamilyParser:
    """Test the UrbanFamilyParser class."""
    
    @pytest.fixture
    def brewery(self):
        """Create a test brewery for Urban Family."""
        return Brewery(
            key="urban-family",
            name="Urban Family Brewing",
            url="https://app.hivey.io/urbanfamily/public-calendar",
            parser_config={
                "api_endpoint": "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar",
                "api_type": "hivey_calendar"
            }
        )
    
    @pytest.fixture
    def parser(self, brewery):
        """Create a parser instance."""
        return UrbanFamilyParser(brewery)
    
    @pytest.fixture
    def sample_api_response(self):
        """Sample API response with food truck events."""
        return [
            {
                "_id": {"$oid": "67f70d76e4ca31e444ef63eb"},
                "applicantVendors": [
                    {
                        "applicationType": "manuallyAdded",
                        "status": "confirmed",
                        "vendorId": "67f6f627e4ca31e444ef637e"
                    }
                ],
                "associatedVenue": {"$oid": "67edae71e9f3be17e2ef6380"},
                "eventDates": [
                    {
                        "date": "July 06, 2025",
                        "endTime": "19:00",
                        "startTime": "13:00"
                    }
                ],
                "eventDescription": "",
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/kaosamia.png",
                "eventStatus": "upcoming",
                "eventTitle": "FOOD TRUCK - Kaosamia Thai",
                "isApplicationOpen": True,
                "isPublished": True,
                "location": "Urban Family Brewing (1103 NW 52nd st, seattle, Washington)"
            },
            {
                "_id": {"$oid": "67f703a7e4ca31e444ef6394"},
                "applicantVendors": [
                    {
                        "applicationType": "manuallyAdded",
                        "status": "confirmed",
                        "vendorId": "67f6f44de4ca31e444ef637d"
                    }
                ],
                "associatedVenue": {"$oid": "67edae71e9f3be17e2ef6380"},
                "eventDates": [
                    {
                        "date": "July 07, 2025",
                        "endTime": "20:00",
                        "startTime": "16:00"
                    }
                ],
                "eventDescription": "",
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/UpdatedLogo_BLK.png",
                "eventStatus": "upcoming",
                "eventTitle": "FOOD TRUCK",
                "isApplicationOpen": True,
                "isPublished": True,
                "location": "Urban Family Brewing (1103 NW 52nd st, seattle, Washington)"
            }
        ]
    
    @pytest.fixture
    def sample_api_response_with_image_names(self):
        """API response where food truck names need to be extracted from image URLs."""
        return [
            {
                "_id": {"$oid": "test1"},
                "applicantVendors": [{"status": "confirmed"}],
                "eventDates": [{"date": "July 08, 2025", "startTime": "16:00", "endTime": "20:00"}],
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/georgia_greek_logo.jpg",
                "eventTitle": "FOOD TRUCK",
                "eventStatus": "upcoming"
            },
            {
                "_id": {"$oid": "test2"},
                "applicantVendors": [{"status": "confirmed"}],
                "eventDates": [{"date": "July 09, 2025", "startTime": "13:00", "endTime": "19:00"}],
                "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/woodshop_bbq.png",
                "eventTitle": "FOOD TRUCK",
                "eventStatus": "upcoming"
            }
        ]
    
    @pytest.mark.asyncio
    async def test_parse_success_with_api_data(self, parser, sample_api_response):
        """Test successful parsing of API data."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
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
        
        # Check second event (no valid name, should be TBD)
        event2 = events[1]
        assert event2.brewery_key == "urban-family"
        assert event2.brewery_name == "Urban Family Brewing"
        assert event2.food_truck_name == "TBD"  # Generic filename filtered out, using TBD
        assert event2.date == datetime(2025, 7, 7)
        assert event2.start_time == datetime(2025, 7, 7, 16, 0)
        assert event2.end_time == datetime(2025, 7, 7, 20, 0)
    
    @pytest.mark.asyncio
    async def test_parse_with_image_name_extraction(self, parser, sample_api_response_with_image_names):
        """Test food truck name extraction from image URLs."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        with aioresponses() as m:
            m.get(api_url, status=200, payload=sample_api_response_with_image_names)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
        
        assert len(events) == 2
        
        # Check name extraction from image filenames
        assert events[0].food_truck_name == "Georgia Greek Logo"
        assert events[1].food_truck_name == "Woodshop Bbq"
    
    @pytest.mark.asyncio
    async def test_parse_empty_response(self, parser):
        """Test parsing empty API response."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        with aioresponses() as m:
            m.get(api_url, status=200, payload=[])
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
        
        assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_parse_api_error_404(self, parser):
        """Test handling of 404 error from API."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        with aioresponses() as m:
            m.get(api_url, status=404)
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="API endpoint not found \\(404\\)"):
                    await parser.parse(session)
    
    @pytest.mark.asyncio
    async def test_parse_api_error_403(self, parser):
        """Test handling of 403 error from API."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        with aioresponses() as m:
            m.get(api_url, status=403)
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Access forbidden \\(403\\)"):
                    await parser.parse(session)
    
    @pytest.mark.asyncio
    async def test_parse_api_error_500(self, parser):
        """Test handling of 500 error from API."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        with aioresponses() as m:
            m.get(api_url, status=500)
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Server error \\(500\\)"):
                    await parser.parse(session)
    
    @pytest.mark.asyncio
    async def test_parse_invalid_json_response(self, parser):
        """Test handling of invalid JSON response."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        with aioresponses() as m:
            m.get(api_url, status=200, body="invalid json")
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Invalid JSON response from API"):
                    await parser.parse(session)
    
    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser):
        """Test handling of network errors."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        with aioresponses() as m:
            m.get(api_url, exception=aiohttp.ClientError("Network error"))
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Network error fetching Urban Family API"):
                    await parser.parse(session)
    
    @pytest.mark.asyncio
    async def test_parse_filters_invalid_events(self, parser):
        """Test that invalid events are filtered out."""
        api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"
        
        invalid_events = [
            {
                # Missing eventDates
                "_id": {"$oid": "invalid1"},
                "eventTitle": "FOOD TRUCK - Valid Name",
                "eventStatus": "upcoming"
            },
            {
                # Missing food truck name
                "_id": {"$oid": "invalid2"},
                "eventDates": [{"date": "July 10, 2025", "startTime": "16:00", "endTime": "20:00"}],
                "eventTitle": "FOOD TRUCK",
                "eventImage": "https://example.com/logo.png",
                "eventStatus": "upcoming"
            },
            {
                # Valid event
                "_id": {"$oid": "valid1"},
                "eventDates": [{"date": "July 11, 2025", "startTime": "16:00", "endTime": "20:00"}],
                "eventTitle": "FOOD TRUCK - Good Eats",
                "eventStatus": "upcoming"
            }
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
    
    def test_extract_food_truck_name_from_title(self, parser):
        """Test food truck name extraction from event title."""
        # Test explicit name in title
        item1 = {"eventTitle": "FOOD TRUCK - Awesome Tacos"}
        assert parser._extract_food_truck_name(item1) == "Awesome Tacos"
        
        # Test title that's not just "FOOD TRUCK"
        item2 = {"eventTitle": "Special Event - Pizza Night"}
        assert parser._extract_food_truck_name(item2) == "Special Event - Pizza Night"
        
        # Test generic "FOOD TRUCK" title (should return None for this test)
        item3 = {"eventTitle": "FOOD TRUCK"}
        assert parser._extract_food_truck_name(item3) is None
    
    def test_extract_food_truck_name_from_image_url(self, parser):
        """Test food truck name extraction from image URL."""
        item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/awesome_tacos_logo.jpg"
        }
        result = parser._extract_food_truck_name(item)
        assert result == "Awesome Tacos Logo"
    
    def test_extract_food_truck_name_no_valid_name(self, parser):
        """Test when no valid food truck name can be extracted."""
        item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/logo.png"
        }
        assert parser._extract_food_truck_name(item) is None
    
    def test_parse_urban_family_date_formats(self, parser):
        """Test parsing various date formats."""
        # Standard format
        assert parser._parse_urban_family_date("July 06, 2025") == datetime(2025, 7, 6)
        
        # Without comma
        assert parser._parse_urban_family_date("July 06 2025") == datetime(2025, 7, 6)
        
        # Different month
        assert parser._parse_urban_family_date("December 25, 2025") == datetime(2025, 12, 25)
        
        # Invalid format should return None
        assert parser._parse_urban_family_date("invalid date") is None
    
    def test_parse_time_string_24_hour_format(self, parser):
        """Test parsing 24-hour time format."""
        test_date = datetime(2025, 7, 6)
        
        # Standard 24-hour format
        assert parser._parse_time_string("13:00", test_date) == datetime(2025, 7, 6, 13, 0)
        assert parser._parse_time_string("19:30", test_date) == datetime(2025, 7, 6, 19, 30)
        assert parser._parse_time_string("09:15", test_date) == datetime(2025, 7, 6, 9, 15)
        
        # Edge cases
        assert parser._parse_time_string("00:00", test_date) == datetime(2025, 7, 6, 0, 0)
        assert parser._parse_time_string("23:59", test_date) == datetime(2025, 7, 6, 23, 59)
    
    def test_parse_time_string_12_hour_format(self, parser):
        """Test parsing 12-hour time format with AM/PM."""
        test_date = datetime(2025, 7, 6)
        
        # PM times
        assert parser._parse_time_string("1:00 pm", test_date) == datetime(2025, 7, 6, 13, 0)
        assert parser._parse_time_string("12:30 PM", test_date) == datetime(2025, 7, 6, 12, 30)
        
        # AM times
        assert parser._parse_time_string("8:00 am", test_date) == datetime(2025, 7, 6, 8, 0)
        assert parser._parse_time_string("12:00 AM", test_date) == datetime(2025, 7, 6, 0, 0)
    
    def test_parse_time_string_invalid_formats(self, parser):
        """Test parsing invalid time formats."""
        test_date = datetime(2025, 7, 6)
        
        # Invalid times should return None
        assert parser._parse_time_string("25:00", test_date) is None
        assert parser._parse_time_string("12:70", test_date) is None
        assert parser._parse_time_string("invalid", test_date) is None
        assert parser._parse_time_string("", test_date) is None
    
    def test_extract_times_from_event_dates(self, parser):
        """Test time extraction from eventDates structure."""
        test_date = datetime(2025, 7, 6)
        
        item = {
            "eventDates": [
                {
                    "date": "July 06, 2025",
                    "startTime": "13:00",
                    "endTime": "19:00"
                }
            ]
        }
        
        start_time, end_time = parser._extract_times(item, test_date)
        assert start_time == datetime(2025, 7, 6, 13, 0)
        assert end_time == datetime(2025, 7, 6, 19, 0)
    
    def test_extract_times_missing_data(self, parser):
        """Test time extraction when data is missing."""
        test_date = datetime(2025, 7, 6)
        
        # Missing eventDates
        item1 = {}
        start_time, end_time = parser._extract_times(item1, test_date)
        assert start_time is None
        assert end_time is None
        
        # Empty eventDates
        item2 = {"eventDates": []}
        start_time, end_time = parser._extract_times(item2, test_date)
        assert start_time is None
        assert end_time is None
        
        # Missing time fields
        item3 = {"eventDates": [{"date": "July 06, 2025"}]}
        start_time, end_time = parser._extract_times(item3, test_date)
        assert start_time is None
        assert end_time is None
    
    def test_parse_json_data_dict_format(self, parser):
        """Test parsing JSON data in dict format with 'events' key."""
        data = {
            "events": [
                {
                    "eventTitle": "FOOD TRUCK - Test Truck",
                    "eventDates": [{"date": "July 06, 2025", "startTime": "13:00", "endTime": "19:00"}],
                    "eventStatus": "upcoming"
                }
            ]
        }
        
        events = parser._parse_json_data(data)
        assert len(events) == 1
        assert events[0].food_truck_name == "Test Truck"
    
    def test_parse_json_data_invalid_structure(self, parser):
        """Test parsing invalid JSON data structure."""
        # String data should be handled gracefully (returns empty list)
        events = parser._parse_json_data("invalid data")
        assert events == []
        
        # Number data should be handled gracefully (returns empty list)
        events = parser._parse_json_data(123)
        assert events == []