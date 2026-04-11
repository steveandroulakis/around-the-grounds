"""Generate contextual haikus about food truck scenes using Claude AI."""

import asyncio
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

import anthropic

from ..models import Event


DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "haiku_prompt.txt"
)

DEFAULT_PROMPT_TEMPLATE = """Today's date is: {date}
Time of day: {time_of_day}
Current weather in Ballard, Seattle: {weather}

Today's featured food truck: {truck_name} at {venue_name}

Today's haiku inspiration:
{events_summary}

---

Create a haiku (5-7-5 syllable structure) that captures the essence of today's food truck scene in Seattle's Ballard neighborhood. Your haiku should:

1. Let the weather seep into the imagery naturally — through textures, moods, and sensory details — rather than stating it directly
2. Feature the specific food truck ({truck_name}) and brewery ({venue_name}) mentioned above
3. Evoke the atmosphere of gathering at local breweries and food spots
4. Balance concrete sensory details with weather-driven imagery

Stay faithful to what's described — do not invent or embellish sensory details beyond what the data supports. If it's not raining, don't say "damp." If there's no fog, don't say "misty." If humidity is moderate, don't exaggerate it. Only describe conditions that are clearly present in the weather provided. Don't invent what people are wearing or other details not in the data.

When precipitation is described as a "chance" with a percentage, treat it as a possibility — not a certainty. Capture the anticipation or threat of weather rather than stating it as fact (e.g. "skies threaten rain" or "clouds may break" rather than "rain soaks the line").

Use the food truck's actual name — don't riff on or pun on the name.

Avoid starting with the most obvious weather description (e.g. don't just say "gray skies" for overcast). Find unexpected angles — how the weather affects sounds, smells, textures, people's behavior, or the food itself.

The haiku should feel authentic to the Pacific Northwest experience and celebrate the diversity of street food culture. Avoid being overly literal - aim for evocative, poetic language that honors the traditional haiku form.

CRITICAL FORMATTING REQUIREMENTS:
- The haiku MUST be exactly 3 lines of text
- Each line must contain actual words, not just emojis
- The haiku MUST start with an emoji at the BEGINNING of the first line AND end with an emoji at the END of the third line (inline with the text)
- Do NOT put emojis on their own separate lines
- Good examples:

🌧️ Spring rain has moods low—
Plaza Garcia's warmth glows
at Obec's wood door 🍺

☀️ Tacos sizzle bright
at Stoup beneath golden rays,
summer haze and hops 🍺

🍖 Brisket smoke and hops—
Johnson's plates at Stoup's long pour,
IPAs run cold 🍺

☁️ Where Ya At Matt's spice
cuts the soft gray afternoon—
Stoup pints, warm inside 🍺

🥪 Wich Came First's warmth pulls—
Yonder's cider, Bale Breaker,
coats up, bar stools full 🍺

🌙 Night falls on Ballard—
Where Ya At Matt's last orders,
stout warms the long dark 🍺

Return only the haiku with inline emoji, nothing else."""


class HaikuGenerator:
    """Generates haikus about food truck events using Claude Sonnet."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        prompt_path: Optional[Union[str, Path]] = None,
        prompt_template: Optional[str] = None,
    ):
        """Initialize haiku generator with Anthropic API client."""
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key
        )  # Uses ANTHROPIC_API_KEY env var if None
        self.logger = logging.getLogger(__name__)
        self.prompt_template = (
            prompt_template
            if prompt_template
            else self._load_prompt_template(prompt_path)
        )

    async def generate_haiku(
        self,
        date: datetime,
        events: List[Event],
        max_retries: int = 2,
        site_name: str = "Food Trucks",
    ) -> Optional[str]:
        """
        Generate a haiku based on today's food truck events.

        Args:
            date: The date for the haiku context
            events: List of food truck events for today
            max_retries: Maximum number of retry attempts
            site_name: Name of the site requesting the haiku. Currently
                accepted for API parity with the multi-site caller, but the
                Ballard prompt template is weather- and Ballard-specific;
                this parameter is not interpolated into that template.

        Returns:
            Haiku string with emojis and 3 lines, or None if generation fails
        """
        if not events:
            self.logger.debug("No events provided for haiku generation")
            return None

        # Retry logic for network issues
        for attempt in range(max_retries + 1):
            try:
                haiku = await self._generate_haiku_internal(date, events)

                if haiku:
                    self.logger.info(f"Generated haiku: {haiku}")
                    return haiku
                else:
                    self.logger.debug("Could not generate haiku")
                    return None

            except anthropic.APITimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
                self.logger.warning(
                    f"Haiku generation timed out after {max_retries} retries"
                )
            except anthropic.APIError as e:
                self.logger.error(f"Anthropic API error: {str(e)}")
                break
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                self.logger.error(f"Error generating haiku: {str(e)}")

        return None

    async def _generate_haiku_internal(
        self, date: datetime, events: List[Event]
    ) -> Optional[str]:
        """Internal method to generate haiku using Claude API."""
        try:
            from .weather import fetch_weather

            # Fetch real-time weather — required for haiku generation
            weather_result = await fetch_weather()
            if weather_result is None:
                self.logger.warning(
                    "Could not fetch weather data, skipping haiku generation"
                )
                return None

            weather_summary, time_of_day = weather_result

            # Format date for prompt
            date_str = date.strftime("%B %d, %Y (%A)")

            # Randomly select ONE event/venue combination for diversity
            selected_event = random.choice(events)
            truck_name = selected_event.title
            venue_name = selected_event.venue_name

            self.logger.debug(
                f"Selected truck for haiku: {truck_name} at {venue_name}"
            )

            # Build prompt from template
            prompt = self._build_prompt(
                date_str=date_str,
                truck_name=truck_name,
                venue_name=venue_name,
                events=[selected_event],
                weather=weather_summary,
                time_of_day=time_of_day,
            )

            message = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=150,
                temperature=0.85,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Extract the response text
            content_block = message.content[0]
            if hasattr(content_block, "text"):
                response_text = content_block.text.strip()  # type: ignore
            else:
                # Handle different content types by converting to string
                response_text = str(content_block).strip()

            if response_text:
                # Clean up the response (remove extra whitespace, ensure 3 lines)
                cleaned_haiku = self._clean_haiku(response_text)
                if cleaned_haiku:
                    return cleaned_haiku
                else:
                    # Incomplete haiku, raise exception to trigger retry
                    raise ValueError("Received incomplete haiku from API")

            return None

        except Exception as e:
            self.logger.error(f"Claude API error generating haiku: {str(e)}")
            raise  # Re-raise to allow retry logic to handle it

    def _clean_haiku(self, haiku: str) -> Optional[str]:
        """Clean up haiku text to ensure proper formatting."""
        # Split by newlines and filter empty lines
        lines = [line.strip() for line in haiku.split("\n") if line.strip()]

        # Filter out lines that are ONLY emojis/symbols (no alphanumeric content)
        text_lines = [line for line in lines if any(c.isalnum() for c in line)]

        # Haiku must have exactly 3 lines with actual text content
        if len(text_lines) < 3:
            self.logger.warning(
                f"Incomplete haiku received ({len(text_lines)} text lines), rejecting"
            )
            return None

        # Take first 3 text lines
        return "\n".join(text_lines[:3])

    def _load_prompt_template(
        self, prompt_path: Optional[Union[str, Path]] = None
    ) -> str:
        """Load the haiku prompt template with graceful fallbacks."""
        candidate_paths = []

        if prompt_path:
            candidate_paths.append(Path(prompt_path))

        env_path = os.getenv("HAIKU_PROMPT_FILE")
        if env_path:
            candidate_paths.append(Path(env_path))

        candidate_paths.append(DEFAULT_PROMPT_PATH)

        for path in candidate_paths:
            try:
                if path.exists():
                    prompt = path.read_text(encoding="utf-8").strip()
                    if prompt:
                        self.logger.debug(
                            "Loaded haiku prompt template from %s", path.as_posix()
                        )
                        return prompt
                    self.logger.warning(
                        "Haiku prompt template at %s is empty; trying next option",
                        path.as_posix(),
                    )
            except OSError as exc:
                self.logger.warning(
                    "Failed to read haiku prompt template at %s: %s",
                    path.as_posix(),
                    exc,
                )

        self.logger.debug("Using built-in haiku prompt template fallback")
        return DEFAULT_PROMPT_TEMPLATE

    def _build_prompt(
        self,
        *,
        date_str: str,
        truck_name: str,
        venue_name: str,
        events: List[Event],
        weather: str,
        time_of_day: str,
    ) -> str:
        """Render the configured prompt template with context."""
        events_summary = "\n".join(
            f"- {event.title} at {event.venue_name}" for event in events
        )

        template = self.prompt_template
        format_kwargs = dict(
            date=date_str,
            truck_name=truck_name,
            venue_name=venue_name,
            events_summary=events_summary,
            weather=weather,
            time_of_day=time_of_day,
        )

        try:
            return template.format(**format_kwargs)
        except KeyError as exc:
            self.logger.warning(
                "Prompt template missing placeholder %s; falling back to default",
                exc,
            )
        except ValueError as exc:
            # e.g. unmatched braces
            self.logger.warning(
                "Prompt template formatting failed (%s); falling back to default",
                exc,
            )

        return DEFAULT_PROMPT_TEMPLATE.format(**format_kwargs)
