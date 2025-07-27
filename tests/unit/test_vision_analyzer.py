from unittest.mock import Mock, patch

import pytest

from around_the_grounds.utils.vision_analyzer import VisionAnalyzer


class TestVisionAnalyzer:
    @pytest.fixture
    def vision_analyzer(self) -> VisionAnalyzer:
        return VisionAnalyzer()

    def test_is_valid_image_url(self, vision_analyzer: VisionAnalyzer) -> None:
        # Valid image URLs
        assert vision_analyzer._is_valid_image_url("https://example.com/image.jpg")
        assert vision_analyzer._is_valid_image_url(
            "https://s3.amazonaws.com/bucket/image"
        )
        assert vision_analyzer._is_valid_image_url(
            "https://images.example.com/photo.png"
        )
        assert vision_analyzer._is_valid_image_url("https://media.example.com/logo.gif")
        assert vision_analyzer._is_valid_image_url("https://img.example.com/test.webp")

        # Invalid URLs
        assert not vision_analyzer._is_valid_image_url("not-a-url")
        assert not vision_analyzer._is_valid_image_url("")
        assert not vision_analyzer._is_valid_image_url("ftp://example.com/image.jpg")
        assert not vision_analyzer._is_valid_image_url(None)  # type: ignore

    def test_clean_vendor_name(self, vision_analyzer: VisionAnalyzer) -> None:
        # Test removing common suffixes
        assert vision_analyzer._clean_vendor_name("Georgia's Food Truck") == "Georgia's"
        assert vision_analyzer._clean_vendor_name("Marination Kitchen") == "Marination"
        assert vision_analyzer._clean_vendor_name("Simple Name") == "Simple Name"
        assert vision_analyzer._clean_vendor_name("Test Restaurant") == "Test"
        assert vision_analyzer._clean_vendor_name("Coffee Cafe") == "Coffee"
        assert vision_analyzer._clean_vendor_name("Brewery LLC") == "Brewery"

        # Test names that shouldn't be changed
        assert vision_analyzer._clean_vendor_name("Georgia's") == "Georgia's"
        assert vision_analyzer._clean_vendor_name("Marination") == "Marination"

        # Test edge cases
        assert vision_analyzer._clean_vendor_name("  Spaced Name  ") == "Spaced Name"
        assert vision_analyzer._clean_vendor_name("") == ""

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_analyze_image_success(
        self, mock_anthropic: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Mock successful API response
        mock_client = Mock()
        mock_message = Mock()
        mock_message.content = [Mock(text="Georgia's")]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client

        vision_analyzer.client = mock_client

        result = await vision_analyzer.analyze_food_truck_image(
            "https://example.com/georgia.jpg"
        )
        assert result == "Georgia's"

        # Verify the API was called with correct parameters
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["model"] == "claude-sonnet-4-20250514"
        assert call_args[1]["max_tokens"] == 200

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_analyze_image_unknown_response(
        self, mock_anthropic: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Mock "UNKNOWN" response
        mock_client = Mock()
        mock_message = Mock()
        mock_message.content = [Mock(text="UNKNOWN")]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client

        vision_analyzer.client = mock_client

        result = await vision_analyzer.analyze_food_truck_image(
            "https://example.com/unclear.jpg"
        )
        assert result is None

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_analyze_image_with_suffix_cleaning(
        self, mock_anthropic: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Mock response with suffix that should be cleaned
        mock_client = Mock()
        mock_message = Mock()
        mock_message.content = [Mock(text="Georgia's Food Truck")]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client

        vision_analyzer.client = mock_client

        result = await vision_analyzer.analyze_food_truck_image(
            "https://example.com/georgia.jpg"
        )
        assert result == "Georgia's"

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_analyze_image_invalid_url(
        self, mock_anthropic: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Should return None for invalid URLs without calling API
        result = await vision_analyzer.analyze_food_truck_image("not-a-url")
        assert result is None

        result = await vision_analyzer.analyze_food_truck_image("")
        assert result is None

    @pytest.mark.asyncio
    @patch("anthropic.Anthropic")
    async def test_analyze_image_api_error(
        self, mock_anthropic: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Mock API error
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.return_value = mock_client

        vision_analyzer.client = mock_client

        result = await vision_analyzer.analyze_food_truck_image(
            "https://example.com/test.jpg"
        )
        assert result is None

    @pytest.mark.asyncio
    @patch(
        "around_the_grounds.utils.vision_analyzer.VisionAnalyzer._analyze_image_by_url"
    )
    async def test_analyze_image_retry_logic(
        self, mock_analyze: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Mock generic exception that should trigger retry, followed by success
        mock_analyze.side_effect = [Exception("Timeout"), "Georgia's"]

        # Should retry and succeed
        result = await vision_analyzer.analyze_food_truck_image(
            "https://example.com/test.jpg", max_retries=1
        )
        assert result == "Georgia's"

        # Should have been called twice (original + 1 retry)
        assert mock_analyze.call_count == 2

    @pytest.mark.asyncio
    @patch(
        "around_the_grounds.utils.vision_analyzer.VisionAnalyzer._analyze_image_by_url"
    )
    async def test_analyze_image_max_retries_exceeded(
        self, mock_analyze: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Mock persistent errors
        mock_analyze.side_effect = Exception("Persistent error")

        # Should fail after max retries
        result = await vision_analyzer.analyze_food_truck_image(
            "https://example.com/test.jpg", max_retries=1
        )
        assert result is None

        # Should have been called max_retries + 1 times
        assert mock_analyze.call_count == 2

    @pytest.mark.asyncio
    @patch(
        "around_the_grounds.utils.vision_analyzer.VisionAnalyzer._analyze_image_by_url"
    )
    async def test_analyze_image_general_exception_handling(
        self, mock_analyze: Mock, vision_analyzer: VisionAnalyzer
    ) -> None:
        # Mock any kind of exception
        mock_analyze.side_effect = RuntimeError("General API error")

        # Should handle gracefully
        result = await vision_analyzer.analyze_food_truck_image(
            "https://example.com/test.jpg", max_retries=0
        )
        assert result is None

        # Should have been called once
        assert mock_analyze.call_count == 1
