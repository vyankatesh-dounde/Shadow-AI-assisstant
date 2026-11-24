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
        "movie": ("book_movie", ["movie", "time", "people"], ("book", "watch", "see")),
        "restaurant": ("reserve_restaurant", ["restaurant", "date", "time", "people"], ("reserve", "book")),
        "food": ("order_food", ["restaurant", "items"], ("order", "deliver", "delivery", "buy")),
    }

    def plan(self, text: str) -> Plan:
        lower = text.casefold()
        for keyword, (intent, required, triggers) in self.TASKS.items():
            if keyword in lower and any(re.search(rf"\b{trigger}\b", lower) for trigger in triggers):
                slots: dict[str, Any] = {}
                if "tonight" in lower:
                    slots["date"] = "tonight"
                people = re.search(r"\b(\d+)\s+(?:people|person|tickets?)\b", lower)
                if people:
                    slots["people"] = int(people.group(1))
                return Plan(intent=intent, task=keyword, slots=slots, required_slots=required)
        return Plan()
