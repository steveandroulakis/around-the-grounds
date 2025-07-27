"""Unit tests for data models."""

from datetime import datetime

from around_the_grounds.models import Brewery, FoodTruckEvent


class TestBrewery:
    """Test the Brewery model."""

    def test_brewery_creation(self) -> None:
        """Test basic brewery creation."""
        brewery = Brewery(
            key="test-key", name="Test Brewery", url="https://example.com"
        )

        assert brewery.key == "test-key"
        assert brewery.name == "Test Brewery"
        assert brewery.url == "https://example.com"
        assert brewery.parser_config == {}

    def test_brewery_with_config(self) -> None:
        """Test brewery creation with parser config."""
        config = {"test": "value"}
        brewery = Brewery(
            key="test-key",
            name="Test Brewery",
            url="https://example.com",
            parser_config=config,
        )

        assert brewery.parser_config == config

    def test_brewery_equality(self) -> None:
        """Test brewery equality comparison."""
        brewery1 = Brewery("key1", "Name1", "url1")
        brewery2 = Brewery("key1", "Name1", "url1")
        brewery3 = Brewery("key2", "Name1", "url1")

        assert brewery1 == brewery2
        assert brewery1 != brewery3


class TestFoodTruckEvent:
    """Test the FoodTruckEvent model."""

    def test_food_truck_event_creation(self) -> None:
        """Test basic food truck event creation."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)

        event = FoodTruckEvent(
            brewery_key="test-brewery",
            brewery_name="Test Brewery",
            food_truck_name="Test Truck",
            date=event_date,
        )

        assert event.brewery_key == "test-brewery"
        assert event.brewery_name == "Test Brewery"
        assert event.food_truck_name == "Test Truck"
        assert event.date == event_date
        assert event.start_time is None
        assert event.end_time is None
        assert event.description is None

    def test_food_truck_event_with_times(self) -> None:
        """Test food truck event with start and end times."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)
        start_time = datetime(2025, 7, 5, 13, 0, 0)
        end_time = datetime(2025, 7, 5, 20, 0, 0)

        event = FoodTruckEvent(
            brewery_key="test-brewery",
            brewery_name="Test Brewery",
            food_truck_name="Test Truck",
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            description="Test description",
        )

        assert event.start_time == start_time
        assert event.end_time == end_time
        assert event.description == "Test description"

    def test_food_truck_event_equality(self) -> None:
        """Test food truck event equality comparison."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)

        event1 = FoodTruckEvent("key1", "Name1", "Truck1", event_date)
        event2 = FoodTruckEvent("key1", "Name1", "Truck1", event_date)
        event3 = FoodTruckEvent("key2", "Name1", "Truck1", event_date)

        assert event1 == event2
        assert event1 != event3

    def test_food_truck_event_string_representation(self) -> None:
        """Test string representation of food truck event."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)

        event = FoodTruckEvent(
            brewery_key="test-brewery",
            brewery_name="Test Brewery",
            food_truck_name="Test Truck",
            date=event_date,
        )

        str_repr = str(event)
        assert "Test Truck" in str_repr
        assert "Test Brewery" in str_repr
