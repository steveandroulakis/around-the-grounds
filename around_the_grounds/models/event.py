from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    """
    Generalized event (replaces FoodTruckEvent for multi-domain support).

    Supports any type of event - food trucks, concerts, community events, etc.
    """
    source_key: str
    source_name: str
    event_name: str
    date: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    event_category: str = "food"  # "food", "music", "family", "community", etc.
    ai_generated_name: bool = False

    def __str__(self) -> str:
        date_str = self.date.strftime("%Y-%m-%d") if self.date else "None"
        time_str = ""
        if self.start_time:
            time_str = f" {self.start_time.strftime('%H:%M')}"
            if self.end_time:
                time_str += f"-{self.end_time.strftime('%H:%M')}"

        return f"{date_str}{time_str}: {self.event_name} @ {self.source_name}"