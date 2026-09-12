import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Plan:
    intent: str | None = None
    task: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    required_slots: list[str] = field(default_factory=list)


class Planner:
    TASKS = {
        "movie": ("book_movie", ["movie", "time", "people"]),
        "restaurant": ("reserve_restaurant", ["restaurant", "date", "time", "people"]),
        "food": ("order_food", ["restaurant", "items"]),
    }

    def plan(self, text: str) -> Plan:
        lower = text.casefold()
        for keyword, (intent, required) in self.TASKS.items():
            if keyword in lower and any(word in lower for word in ("book", "watch", "reserve", "order", "eat")):
                slots: dict[str, Any] = {}
                if "tonight" in lower:
                    slots["date"] = "tonight"
                people = re.search(r"\b(\d+)\s+(?:people|person|tickets?)\b", lower)
                if people:
                    slots["people"] = int(people.group(1))
                return Plan(intent=intent, task=keyword, slots=slots, required_slots=required)
        return Plan()
