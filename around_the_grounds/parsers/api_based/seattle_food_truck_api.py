import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from ..models import Brewery, FoodTruckEvent
from ..utils.timezone_utils import now_in_pacific_naive, utc_to_pacific_naive
from ..base import BaseParser


class SeattleFoodTruckApiParser(BaseParser):
    """
    Parser for the Seattle Food Truck API (seattlefoodtruck.com).

    This parser fetches food truck schedule data from seattlefoodtruck.com's
    RESTful JSON API, which provides comprehensive event information including
    booked trucks, waitlists, and precise timing details.
    Can be used by any location that uses this API service.
    """

    BASE_URL = "https://www.seattlefoodtruck.com/api/events"
    LOCATION_ID = 164  # Saleh's Corner location ID

    def __init__(self, brewery: Brewery) -> None:
        super().__init__(brewery)

    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        """
        Parse food truck events from Saleh's Corner API.

        Returns events for the next 7 days with confirmed bookings only.
        """
        try:
            # Get date range for API request
            start_date_str, end_date_str = self._get_api_date_range()

            # Construct API parameters
            params = {
                "page": 1,
                "page_size": 300,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "for_locations": self.LOCATION_ID,
                "with_active_trucks": "true",
                "include_bookings": "true",
            }

            self.logger.debug(f"Fetching API data from: {self.BASE_URL}")
            self.logger.debug(f"API parameters: {params}")

            # Fetch data from API
            async with session.get(self.BASE_URL, params=params) as response:
                if response.status == 404:
                    raise ValueError(f"API endpoint not found (404): {self.BASE_URL}")
                elif response.status == 403:
                    raise ValueError(f"Access forbidden (403): {self.BASE_URL}")
                elif response.status == 429:
                    raise ValueError(
                        "Rate limited (429): Too many requests to Saleh's API"
                    )
                elif response.status == 500:
                    raise ValueError(f"Server error (500): {self.BASE_URL}")
                elif response.status != 200:
                    raise ValueError(f"HTTP {response.status}: {self.BASE_URL}")

                # Parse JSON response
                try:
                    data = await response.json()
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON response from API: {str(e)}")

                if not data:
                    self.logger.info("Empty response from API - no events found")
                    return []

                self.logger.debug(
                    f"Received JSON data with {len(data.get('events', []))} events"
                )

                # Parse events from JSON data
                events = self._parse_api_events(data)

                # Filter and validate events
                valid_events = self.filter_valid_events(events)
                self.logger.info(
                    f"Parsed {len(valid_events)} valid events from {len(events)} total"
                )
                return valid_events

        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching Saleh's Corner API: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error parsing Saleh's Corner: {str(e)}")
            if isinstance(e, ValueError):
                raise  # Re-raise our custom ValueError messages
            raise ValueError(f"Failed to parse Saleh's Corner API: {str(e)}")

    def _get_api_date_range(self, days_ahead: int = 7) -> Tuple[str, str]:
        """
        Calculate start and end dates for API request in M-D-YY format.

        Args:
            days_ahead: Number of days to look ahead (default: 7)

        Returns:
            Tuple of (start_date_str, end_date_str) in M-D-YY format
        """
        # Use Pacific timezone for date calculations
        today = now_in_pacific_naive()
        end_date = today + timedelta(days=days_ahead)

        # Format for API (M-D-YY)
        start_str = f"{today.month}-{today.day}-{today.year % 100}"
        end_str = f"{end_date.month}-{end_date.day}-{end_date.year % 100}"

        return start_str, end_str

    def _parse_api_events(self, api_data: Dict[str, Any]) -> List[FoodTruckEvent]:
        """
        Parse events from API JSON response.

        Args:
            api_data: JSON response from the API

        Returns:
            List of FoodTruckEvent objects
        """
        events = []

        try:
            events_list = api_data.get("events", [])
            if not isinstance(events_list, list):
                self.logger.warning("API response 'events' is not a list")
                return []

            for event_data in events_list:
                event = self._parse_single_event(event_data)
                if event:
                    events.append(event)

        except Exception as e:
            self.logger.error(f"Error parsing API events: {str(e)}")
            raise ValueError(f"Failed to parse event data: {str(e)}")

        return events

    def _parse_single_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[FoodTruckEvent]:
        """
        Parse a single event from the API response.

        Args:
            event_data: Single event object from API response

        Returns:
            FoodTruckEvent object or None if event is invalid
        """
        try:
            # Skip events without bookings
            bookings = event_data.get("bookings", [])
            if not bookings or not isinstance(bookings, list) or len(bookings) == 0:
                self.logger.debug(
                    f"Skipping event without bookings: {event_data.get('id')}"
                )
                return None

            # Get the first approved booking
            booked_truck = None
            for booking in bookings:
                if booking.get("status") == "approved" and "truck" in booking:
                    booked_truck = booking["truck"]
                    break

            if not booked_truck:
                self.logger.debug(
                    f"Skipping event without approved booking: {event_data.get('id')}"
                )
                return None

            # Extract vendor name
            vendor_name = self._extract_vendor_name(booked_truck)
            if not vendor_name:
                self.logger.warning(f"No vendor name in event {event_data.get('id')}")
                vendor_name = "TBD"

            # Parse timestamps
            start_time_dt, end_time_dt = self._parse_event_timestamps(event_data)
            if not start_time_dt:
                self.logger.debug(
                    f"Skipping event without valid start time: {event_data.get('id')}"
                )
                return None

            # Extract additional information
            food_categories = booked_truck.get("food_categories", [])

            # Create description with food categories if available
            description = None
            if food_categories:
                description = f"Cuisine: {', '.join(food_categories)}"

            return FoodTruckEvent(
                brewery_key=self.brewery.key,
                brewery_name=self.brewery.name,
                food_truck_name=vendor_name,
                date=start_time_dt,
                start_time=start_time_dt,
                end_time=end_time_dt,
                description=description,
                ai_generated_name=False,  # Names are provided directly by API
            )

        except Exception as e:
            self.logger.debug(
                f"Error parsing single event: {str(e)}, event: {event_data}"
            )
            return None

    def _extract_vendor_name(self, booked_truck: Dict[str, Any]) -> Optional[str]:
        """
        Extract and clean vendor name from booked truck data.

        Args:
            booked_truck: The 'booked' object from the event

        Returns:
            Cleaned vendor name or None if not found
        """
        name: str = booked_truck.get("name", "").strip()

        # Names in this API are typically clean already
        if name and name.lower() not in ["tbd", "tba", "to be announced", "unknown"]:
            return name

        return None

    def _parse_event_timestamps(
        self, event_data: Dict[str, Any]
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Parse start and end timestamps from event data.

        Args:
            event_data: Event object containing timestamp fields

        Returns:
            Tuple of (start_datetime, end_datetime) or (None, None) if parsing fails
        """
        try:
            # Validate required timestamp fields
            if not event_data.get("start_time") or not event_data.get("end_time"):
                self.logger.warning(
                    f"Missing timestamp fields in event {event_data.get('id')}"
                )
                return None, None

            start_time_str = event_data["start_time"]
            end_time_str = event_data["end_time"]

            # Parse ISO 8601 timestamps
            start_time = self._parse_iso_timestamp(start_time_str)
            end_time = self._parse_iso_timestamp(end_time_str)

            # Validate logical time order
            if start_time and end_time and end_time <= start_time:
                self.logger.warning(
                    f"Invalid time range in event {event_data.get('id')}: {start_time} to {end_time}"
                )
                return None, None

            # Validate times are not too far in the past
            if start_time:
                now = now_in_pacific_naive()
                if start_time.date() < (now.date() - timedelta(days=1)):
                    self.logger.debug(f"Skipping past event: {start_time}")
                    return None, None

            return start_time, end_time

        except Exception as e:
            self.logger.warning(f"Error parsing timestamps: {str(e)}")
            return None, None

    def _parse_iso_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse ISO 8601 timestamp and convert to Pacific timezone.

        Args:
            timestamp_str: ISO 8601 timestamp string

        Returns:
            Timezone-naive datetime in Pacific time or None if parsing fails
        """
        try:
            # Parse ISO format: "2025-08-02T17:00:00.000-07:00"
            dt = datetime.fromisoformat(timestamp_str)

            # Convert to Pacific timezone and make naive for compatibility
            if dt.tzinfo is not None:
                return utc_to_pacific_naive(
                    dt.astimezone(tz=None)
                )  # Convert to UTC first, then to Pacific
            else:
                # If no timezone info, assume it's already in Pacific time
                return dt

        except ValueError as e:
            self.logger.debug(
                f"Error parsing ISO timestamp '{timestamp_str}': {str(e)}"
            )
            return None
