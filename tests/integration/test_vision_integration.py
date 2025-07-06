import pytest
from unittest.mock import Mock, patch, AsyncMock
from around_the_grounds.parsers.urban_family import UrbanFamilyParser
from around_the_grounds.models.brewery import Brewery


class TestVisionIntegration:
    @pytest.fixture
    def parser(self):
        brewery = Brewery(key="urban-family", name="Urban Family", url="https://test.com")
        return UrbanFamilyParser(brewery)
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_vision_fallback_in_parser(self, mock_vision, parser):
        # Mock vision analysis returning a vendor name
        mock_vision.return_value = "Georgia's"
        
        # Test item with no text vendor name but has image with filename that gets filtered out
        test_item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/logo_main_updated.jpg",  # Filename that should be filtered
            "applicantVendors": []
        }
        
        result, ai_generated = parser._extract_food_truck_name(test_item)
        assert result == "Georgia's"
        assert ai_generated == True
        mock_vision.assert_called_once_with("https://example.com/logo_main_updated.jpg")
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_text_extraction_takes_precedence(self, mock_vision, parser):
        # Mock vision analysis (should not be called if text extraction works)
        mock_vision.return_value = "Vision Result"
        
        # Test item with clear text vendor name
        test_item = {
            "eventTitle": "FOOD TRUCK - Marination",
            "eventImage": "https://example.com/some-logo.jpg",
            "applicantVendors": []
        }
        
        result, ai_generated = parser._extract_food_truck_name(test_item)
        assert result == "Marination"
        assert ai_generated == False
        # Vision analysis should not be called when text extraction succeeds
        mock_vision.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_fallback_to_tbd_when_vision_fails(self, mock_vision, parser):
        # Mock vision analysis failing
        mock_vision.return_value = None
        
        test_item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/logo_main_updated.jpg",  # Filename that gets filtered
            "applicantVendors": []
        }
        
        result, ai_generated = parser._extract_food_truck_name(test_item)
        assert result is None
        assert ai_generated == False
        mock_vision.assert_called_once_with("https://example.com/logo_main_updated.jpg")
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_no_vision_when_no_image(self, mock_vision, parser):
        # Test item with no image - should not call vision analysis
        test_item = {
            "eventTitle": "FOOD TRUCK",
            "applicantVendors": []
        }
        
        result, ai_generated = parser._extract_food_truck_name(test_item)
        assert result is None
        assert ai_generated == False
        # Vision analysis should not be called when no image is available
        mock_vision.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_vision_exception_handling(self, mock_vision, parser):
        # Mock vision analysis raising an exception
        mock_vision.side_effect = Exception("Vision API Error")
        
        test_item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/logo_main_updated.jpg",  # Filename that gets filtered
            "applicantVendors": []
        }
        
        # Should handle exception gracefully and fall back to TBD
        result, ai_generated = parser._extract_food_truck_name(test_item)
        assert result is None
        assert ai_generated == False
        mock_vision.assert_called_once_with("https://example.com/logo_main_updated.jpg")
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_vision_with_complex_text_extraction(self, mock_vision, parser):
        # Test that vision is only called when ALL text methods fail
        mock_vision.return_value = "Vision Extracted Name"
        
        # Test item where filename extraction might work but is filtered out
        test_item = {
            "eventTitle": "FOOD TRUCK",  # Generic title
            "eventImage": "https://example.com/logo_updated_main.jpg",  # Filename that gets filtered
            "applicantVendors": []
        }
        
        result, ai_generated = parser._extract_food_truck_name(test_item)
        assert result == "Vision Extracted Name"
        assert ai_generated == True
        mock_vision.assert_called_once_with("https://example.com/logo_updated_main.jpg")
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_vision_with_filename_extraction_success(self, mock_vision, parser):
        # Test that vision is NOT called when filename extraction succeeds
        mock_vision.return_value = "Vision Result"
        
        # Test item where filename extraction should work
        test_item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/georgias_greek_food.jpg",  # Good filename
            "applicantVendors": []
        }
        
        result, ai_generated = parser._extract_food_truck_name(test_item)
        # Should extract from filename, not use vision
        assert result == "Georgias Greek Food"
        assert ai_generated == False
        mock_vision.assert_not_called()
    
    def test_vision_analyzer_lazy_initialization(self, parser):
        # Test that vision analyzer is only created when needed
        assert parser._vision_analyzer is None
        
        # Access the property to trigger initialization
        analyzer = parser.vision_analyzer
        assert analyzer is not None
        assert parser._vision_analyzer is analyzer
        
        # Second access should return the same instance
        analyzer2 = parser.vision_analyzer
        assert analyzer2 is analyzer