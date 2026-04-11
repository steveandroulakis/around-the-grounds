"""Unit tests for haiku generator."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from around_the_grounds.models import Event
from around_the_grounds.utils.haiku_generator import HaikuGenerator


@pytest.fixture
def sample_events() -> list:
    """Create sample food truck events for testing."""
    return [
        Event(
            venue_key="stoup-ballard",
            venue_name="Stoup Brewing",
            title="Georgia's Greek",
            date=datetime(2025, 10, 13),
            start_time=datetime(2025, 10, 13, 17, 0),
            end_time=datetime(2025, 10, 13, 21, 0),
        ),
        Event(
            venue_key="urban-family",
            venue_name="Urban Family Brewing",
            title="MomoExpress",
            date=datetime(2025, 10, 13),
            start_time=datetime(2025, 10, 13, 18, 0),
            end_time=datetime(2025, 10, 13, 22, 0),
        ),
    ]


@pytest.fixture
def haiku_generator() -> HaikuGenerator:
    """Create HaikuGenerator instance for testing."""
    return HaikuGenerator(api_key="test-key")


MOCK_WEATHER = ("53°F, overcast, light breeze, 66% humidity", "Afternoon")
WEATHER_PATCH = "around_the_grounds.utils.weather.fetch_weather"
ANTHROPIC_PATCH = "around_the_grounds.utils.haiku_generator.anthropic.AsyncAnthropic"


class TestHaikuGenerator:
    """Test haiku generation functionality."""

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=MOCK_WEATHER)
    @patch(ANTHROPIC_PATCH)
    async def test_generate_haiku_success(
        self, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test successful haiku generation."""
        # Mock the API response
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "🍂 Autumn breeze whispers\n🍂\nGeorgia's at Stoup awaits\n🍂\nBrews and warmth unite"
        mock_message.content = [mock_content]

        mock_client_instance = mock_anthropic_client.return_value
        mock_client_instance.messages.create = AsyncMock(return_value=mock_message)
        haiku_generator.client = mock_client_instance

        # Generate haiku
        today = datetime(2025, 10, 13)
        haiku = await haiku_generator.generate_haiku(today, sample_events)

        # Verify result
        assert haiku is not None
        assert "Georgia's" in haiku or "autumn" in haiku.lower()
        assert "\n" in haiku  # Should have multiple lines
        mock_fetch_weather.assert_awaited()

    @pytest.mark.asyncio
    @patch(ANTHROPIC_PATCH)
    async def test_generate_haiku_no_events(
        self, mock_anthropic_client: Mock, haiku_generator: HaikuGenerator
    ) -> None:
        """Test haiku generation with no events."""
        today = datetime(2025, 10, 13)
        haiku = await haiku_generator.generate_haiku(today, [])

        assert haiku is None

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=MOCK_WEATHER)
    @patch(ANTHROPIC_PATCH)
    async def test_generate_haiku_api_timeout(
        self, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test haiku generation with API timeout."""
        import anthropic
        import httpx

        # Mock API timeout error
        mock_client_instance = mock_anthropic_client.return_value
        # Create a mock request for the timeout error
        mock_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        mock_client_instance.messages.create = AsyncMock(
            side_effect=anthropic.APITimeoutError(mock_request)
        )
        haiku_generator.client = mock_client_instance

        # Generate haiku with max_retries=0 for faster test
        today = datetime(2025, 10, 13)
        haiku = await haiku_generator.generate_haiku(today, sample_events, max_retries=0)

        assert haiku is None

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=MOCK_WEATHER)
    @patch(ANTHROPIC_PATCH)
    async def test_generate_haiku_api_error(
        self, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test haiku generation with API error."""
        # Mock API error (generic exception)
        mock_client_instance = mock_anthropic_client.return_value
        mock_client_instance.messages.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        haiku_generator.client = mock_client_instance

        # Generate haiku
        today = datetime(2025, 10, 13)
        haiku = await haiku_generator.generate_haiku(today, sample_events)

        assert haiku is None

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=MOCK_WEATHER)
    @patch(ANTHROPIC_PATCH)
    async def test_generate_haiku_with_retry(
        self, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test haiku generation with retry on generic error."""
        # Mock error on first attempt, success on second
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "🌧️ Rain falls softly down\nMomoExpress awaits us\nWarmth in every bite"
        mock_message.content = [mock_content]

        mock_client_instance = mock_anthropic_client.return_value
        mock_client_instance.messages.create = AsyncMock(
            side_effect=[Exception("Network Error"), mock_message]
        )
        haiku_generator.client = mock_client_instance

        # Generate haiku
        today = datetime(2025, 10, 13)
        haiku = await haiku_generator.generate_haiku(today, sample_events, max_retries=1)

        # Should succeed on retry
        assert haiku is not None
        assert "Rain" in haiku or "MomoExpress" in haiku or "Warmth" in haiku

    def test_clean_haiku(self, haiku_generator: HaikuGenerator) -> None:
        """Test haiku cleaning functionality."""
        # Test with proper 3-line haiku
        haiku = "Line 1\nLine 2\nLine 3"
        cleaned = haiku_generator._clean_haiku(haiku)
        assert cleaned == "Line 1\nLine 2\nLine 3"

        # Test with extra lines (should take first 3)
        haiku = "Line 1\nLine 2\nLine 3\nExtra Line 4\nExtra Line 5"
        cleaned = haiku_generator._clean_haiku(haiku)
        assert cleaned == "Line 1\nLine 2\nLine 3"

        # Test with empty lines
        haiku = "Line 1\n\nLine 2\n\nLine 3"
        cleaned = haiku_generator._clean_haiku(haiku)
        assert cleaned == "Line 1\nLine 2\nLine 3"

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=MOCK_WEATHER)
    @patch(ANTHROPIC_PATCH)
    @patch("around_the_grounds.utils.haiku_generator.random.choice")
    async def test_generate_haiku_includes_truck_and_venue(
        self, mock_random_choice: Mock, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test that haiku generation prompt includes truck names and venues."""
        # Mock random.choice to always select first event for deterministic testing
        mock_random_choice.return_value = sample_events[0]

        # Mock the API response
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Test haiku\nLine two\nLine three"
        mock_message.content = [mock_content]

        mock_client_instance = mock_anthropic_client.return_value
        mock_create = AsyncMock(return_value=mock_message)
        mock_client_instance.messages.create = mock_create
        haiku_generator.client = mock_client_instance

        # Generate haiku
        today = datetime(2025, 10, 13)
        await haiku_generator.generate_haiku(today, sample_events)

        # Verify the prompt included the selected truck and venue
        call_args = mock_create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]

        # Since we mocked random.choice to return first event, verify that truck appears
        assert "Georgia's Greek" in prompt
        assert "Stoup Brewing" in prompt
        assert "October 13, 2025" in prompt

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=None)
    async def test_generate_haiku_returns_none_when_weather_fails(
        self, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test that haiku generation returns None when weather fetch fails."""
        today = datetime(2025, 10, 13)
        haiku = await haiku_generator.generate_haiku(today, sample_events)

        assert haiku is None
        mock_fetch_weather.assert_awaited()

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=MOCK_WEATHER)
    @patch(ANTHROPIC_PATCH)
    @patch("around_the_grounds.utils.haiku_generator.random.choice")
    async def test_prompt_includes_weather_and_time_of_day(
        self, mock_random_choice: Mock, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test that the prompt includes weather and time_of_day from fetch_weather."""
        mock_random_choice.return_value = sample_events[0]

        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Test line one\nTest line two\nTest line three"
        mock_message.content = [mock_content]

        mock_client_instance = mock_anthropic_client.return_value
        mock_create = AsyncMock(return_value=mock_message)
        mock_client_instance.messages.create = mock_create
        haiku_generator.client = mock_client_instance

        today = datetime(2025, 10, 13)
        await haiku_generator.generate_haiku(today, sample_events)

        call_args = mock_create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]

        # Verify weather and time_of_day are in the prompt
        assert "53°F, overcast, light breeze, 66% humidity" in prompt
        assert "Afternoon" in prompt

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=("70°F, clear sky, calm winds, 40% humidity", "Evening"))
    @patch(ANTHROPIC_PATCH)
    @patch("around_the_grounds.utils.haiku_generator.random.choice")
    async def test_prompt_includes_evening_weather(
        self, mock_random_choice: Mock, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test that evening weather context is passed correctly."""
        mock_random_choice.return_value = sample_events[0]

        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Evening line one\nEvening line two\nEvening line three"
        mock_message.content = [mock_content]

        mock_client_instance = mock_anthropic_client.return_value
        mock_create = AsyncMock(return_value=mock_message)
        mock_client_instance.messages.create = mock_create
        haiku_generator.client = mock_client_instance

        today = datetime(2025, 10, 13)
        await haiku_generator.generate_haiku(today, sample_events)

        call_args = mock_create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]

        assert "70°F, clear sky, calm winds, 40% humidity" in prompt
        assert "Evening" in prompt

    def test_build_prompt_with_weather(self, haiku_generator: HaikuGenerator, sample_events: list) -> None:
        """Test _build_prompt includes weather and time_of_day placeholders."""
        prompt = haiku_generator._build_prompt(
            date_str="October 13, 2025 (Monday)",
            truck_name="Georgia's Greek",
            venue_name="Stoup Brewing",
            events=sample_events[:1],
            weather="53°F, overcast, light breeze, 66% humidity",
            time_of_day="Afternoon",
        )

        assert "53°F, overcast, light breeze, 66% humidity" in prompt
        assert "Afternoon" in prompt
        assert "Georgia's Greek" in prompt
        assert "Stoup Brewing" in prompt

    @pytest.mark.asyncio
    @patch(WEATHER_PATCH, new_callable=AsyncMock, return_value=MOCK_WEATHER)
    @patch(ANTHROPIC_PATCH)
    async def test_uses_claude_sonnet_model(
        self, mock_anthropic_client: Mock, mock_fetch_weather: AsyncMock, haiku_generator: HaikuGenerator, sample_events: list
    ) -> None:
        """Test that the generator uses claude-sonnet-4-6 model."""
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Line one here\nLine two here\nLine three here"
        mock_message.content = [mock_content]

        mock_client_instance = mock_anthropic_client.return_value
        mock_create = AsyncMock(return_value=mock_message)
        mock_client_instance.messages.create = mock_create
        haiku_generator.client = mock_client_instance

        today = datetime(2025, 10, 13)
        await haiku_generator.generate_haiku(today, sample_events)

        call_args = mock_create.call_args
        assert call_args.kwargs["model"] == "claude-sonnet-4-6"
        assert call_args.kwargs["temperature"] == 0.85
