#!/usr/bin/env python3
"""Test vision analysis with real Urban Family data."""

import asyncio
import logging
import os
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from around_the_grounds.utils.vision_analyzer import VisionAnalyzer  # noqa: E402


async def test_real_image() -> None:
    """Test with the actual Georgia's image URL."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    analyzer = VisionAnalyzer()

    test_url = "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/MainlogoB_Webpreview_Georgia's.jpg"

    print(f"Analyzing image: {test_url}")
    print("This will make a real API call to Anthropic's Vision API...")

    try:
        result = await analyzer.analyze_food_truck_image(test_url)

        if result:
            print(f"✅ Vision analysis result: '{result}'")
            expected = "Georgia's"
            print(f"🎯 Expected result: '{expected}' - Match: {result == expected}")
        else:
            print("❌ Vision analysis failed or returned no result")

    except Exception as e:
        print(f"❌ Error during vision analysis: {str(e)}")


async def test_multiple_images() -> None:
    """Test with multiple different image types."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    analyzer = VisionAnalyzer()

    # Test images (some may work, some may not - that's expected)
    test_images = [
        {
            "url": "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/MainlogoB_Webpreview_Georgia's.jpg",
            "expected": "Georgia's",
            "description": "Georgia's logo",
        },
        # Add more test URLs here if you have them
    ]

    print("Testing multiple images...")
    print("=" * 50)

    for i, test_case in enumerate(test_images, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"URL: {test_case['url']}")

        try:
            result = await analyzer.analyze_food_truck_image(test_case["url"])

            if result:
                print(f"✅ Result: '{result}'")
                if test_case.get("expected"):
                    expected = test_case["expected"]
                    match = result == expected
                    print(f"🎯 Expected: '{expected}' - Match: {match}")
            else:
                print("❌ No result returned")

        except Exception as e:
            print(f"❌ Error: {str(e)}")

        # Small delay between requests to be polite to the API
        await asyncio.sleep(1)


def main() -> int:
    """Main function to run the tests."""
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("Please set your Anthropic API key:")
        print("export ANTHROPIC_API_KEY='your-key-here'")
        return 1

    print("Vision Analysis Test Script")
    print("=" * 30)
    print("This script will test the vision analysis functionality")
    print("with real images and API calls.\n")

    # Choose which test to run
    test_choice = input(
        "Choose test:\n1. Single image test\n2. Multiple images test\nChoice (1 or 2): "
    ).strip()

    if test_choice == "1":
        asyncio.run(test_real_image())
    elif test_choice == "2":
        asyncio.run(test_multiple_images())
    else:
        print("Invalid choice. Running single image test...")
        asyncio.run(test_real_image())

    return 0


if __name__ == "__main__":
    exit(main())
