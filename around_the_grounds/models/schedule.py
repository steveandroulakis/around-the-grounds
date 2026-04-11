from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    venue_key: str
    venue_name: str
    title: str
    date: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    extraction_method: str = "html"

    def __str__(self) -> str:
        date_str = self.date.strftime("%Y-%m-%d") if self.date else "None"
        time_str = ""
        if self.start_time:
            time_str = f" {self.start_time.strftime('%H:%M')}"
            if self.end_time:
                time_str += f"-{self.end_time.strftime('%H:%M')}"

        return f"{date_str}{time_str}: {self.title} @ {self.venue_name}"
