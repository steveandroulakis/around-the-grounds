"""Integration tests for haiku generation in web data."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from around_the_grounds.main import generate_web_data, _generate_haiku_for_today
from around_the_grounds.models import Event


@pytest.fixture
def sample_events_today() -> list:
    """Create sample food truck events for today."""
    from datetime import date

    today = date.today()
    return [
        Event(
            venue_key="stoup-ballard",
            venue_name="Stoup Brewing",
            title="Georgia's Greek",
            date=datetime(today.year, today.month, today.day),
            start_time=datetime(today.year, today.month, today.day, 17, 0),
            end_time=datetime(today.year, today.month, today.day, 21, 0),
        ),
        Event(
            venue_key="urban-family",
            venue_name="Urban Family Brewing",
            title="MomoExpress",
            date=datetime(today.year, today.month, today.day),
            start_time=datetime(today.year, today.month, today.day, 18, 0),
            end_time=datetime(today.year, today.month, today.day, 22, 0),
        ),
    ]


@pytest.fixture
def sample_events_future() -> list:
    """Create sample food truck events for future dates."""
    return [
        Event(
            venue_key="stoup-ballard",
            venue_name="Stoup Brewing",
            title="Oskar's Pizza",
            date=datetime(2025, 12, 25),
            start_time=datetime(2025, 12, 25, 17, 0),
            end_time=datetime(2025, 12, 25, 21, 0),
        ),
    ]


class TestHaikuIntegration:
    """Test haiku integration with web data generation."""

    @pytest.mark.asyncio
    @patch("around_the_grounds.main.HaikuGenerator")
    async def test_generate_web_data_includes_haiku(
        self, mock_haiku_generator_class: Mock, sample_events_today: list
    ) -> None:
        """Test that web data includes haiku when generated successfully."""
        from unittest.mock import AsyncMock

        # Mock haiku generator with async method
        mock_generator = Mock()
        mock_generator.generate_haiku = AsyncMock(
            return_value="Test haiku\nLine two\nLine three"
        )
        mock_haiku_generator_class.return_value = mock_generator

        # Generate web data
        web_data = await generate_web_data(sample_events_today)

        # Verify haiku is in web data
        assert "haiku" in web_data
        assert web_data["haiku"] is not None
        assert "Test haiku" in web_data["haiku"]

    @pytest.mark.asyncio
    @patch("around_the_grounds.main.HaikuGenerator")
    async def test_generate_web_data_no_haiku_on_error(
        self, mock_haiku_generator_class: Mock, sample_events_today: list
    ) -> None:
        """Test that web data gracefully handles haiku generation errors."""
        from unittest.mock import AsyncMock

        # Mock haiku generator to raise an error
        mock_generator = Mock()
        mock_generator.generate_haiku = AsyncMock(side_effect=Exception("API Error"))
        mock_haiku_generator_class.return_value = mock_generator

        # Generate web data - should not fail
        web_data = await generate_web_data(sample_events_today)

        # Verify haiku is None but data is still valid
        assert "haiku" in web_data
        assert web_data["haiku"] is None
        assert "events" in web_data
        assert len(web_data["events"]) == 2

    @pytest.mark.asyncio
    @patch("around_the_grounds.main.HaikuGenerator")
    async def test_generate_web_data_no_events_today(
        self, mock_haiku_generator_class: Mock, sample_events_future: list
    ) -> None:
        """Test that haiku is None when there are no events today."""
        # Generate web data with only future events
        web_data = await generate_web_data(sample_events_future)

        # Verify no haiku was generated
        assert "haiku" in web_data
        assert web_data["haiku"] is None
        assert "events" in web_data
        assert len(web_data["events"]) == 1

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch(
        "around_the_grounds.utils.weather.fetch_weather",
        new_callable=AsyncMock,
        return_value=("53°F, overcast, light breeze, 66% humidity", "Afternoon"),
    )
    @patch("around_the_grounds.utils.haiku_generator.anthropic.AsyncAnthropic")
    async def test_haiku_for_today_filters_events(
        self,
        mock_anthropic_client: Mock,
        mock_fetch_weather: AsyncMock,
        sample_events_today: list,
        sample_events_future: list,
    ) -> None:
        """Test that _generate_haiku_for_today only uses today's events."""
        from unittest.mock import AsyncMock

        # Mock the API response
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Today's haiku\nWith today's trucks\nNot tomorrow's"
        mock_message.content = [mock_content]

        mock_client_instance = mock_anthropic_client.return_value
        mock_create = AsyncMock(return_value=mock_message)
        mock_client_instance.messages.create = mock_create

        # Combine today and future events
        all_events = sample_events_today + sample_events_future

        # Generate haiku
        haiku = await _generate_haiku_for_today(all_events)

        # Verify haiku was generated
        assert haiku is not None
        assert "Today's haiku" in haiku

        # Verify the prompt only included today's events
        call_args = mock_create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]

        # Should include today's trucks
        assert "Georgia's Greek" in prompt or "MomoExpress" in prompt

        # Should NOT include future events
        assert "Oskar's Pizza" not in prompt
        assert "December 25" not in prompt

    @pytest.mark.asyncio
    @patch("around_the_grounds.main.HaikuGenerator")
    async def test_generate_web_data_preserves_other_fields(
        self, mock_haiku_generator_class: Mock, sample_events_today: list
    ) -> None:
        """Test that haiku addition doesn't affect other web data fields."""
        from unittest.mock import AsyncMock

        # Mock haiku generator with async method
        mock_generator = Mock()
        mock_generator.generate_haiku = AsyncMock(return_value="Test haiku")
        mock_haiku_generator_class.return_value = mock_generator

        # Generate web data
        web_data = await generate_web_data(sample_events_today, error_messages=["Test error"])

        # Verify all expected fields are present
        assert "events" in web_data
        assert "updated" in web_data
        assert "total_events" in web_data
        assert "timezone" in web_data
        assert "timezone_note" in web_data
        assert "errors" in web_data
        assert "haiku" in web_data

        # Verify field values
        assert len(web_data["events"]) == 2
        assert web_data["total_events"] == 2
        assert web_data["timezone"] == "America/Los_Angeles"
        assert "Test error" in web_data["errors"]
        assert web_data["haiku"] == "Test haiku"

    @pytest.mark.asyncio
    @patch("around_the_grounds.main.HaikuGenerator")
    async def test_generate_web_data_empty_events(
        self, mock_haiku_generator_class: Mock
    ) -> None:
        """Test web data generation with no events."""
        # Generate web data with empty events
        web_data = await generate_web_data([])

        # Verify haiku is None (no events to generate from)
        assert "haiku" in web_data
        assert web_data["haiku"] is None
        assert web_data["total_events"] == 0
        assert len(web_data["events"]) == 0
