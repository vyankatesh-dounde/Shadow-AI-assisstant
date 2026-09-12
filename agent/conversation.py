import json
from pathlib import Path
from typing import Any

from .schemas import ConversationState


class ConversationManager:
    def __init__(self, state_file: Path | None = None):
        root = Path(__file__).resolve().parent.parent
        self.state_file = state_file or root / "memory" / "agent_state.json"
        self.state_file.parent.mkdir(exist_ok=True)
        self.state = self._load()

    def _load(self) -> ConversationState:
        try:
            value = json.loads(self.state_file.read_text(encoding="utf-8"))
            return ConversationState.from_dict(value)
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
            return ConversationState()

    def save(self) -> None:
        self.state_file.write_text(
            json.dumps(self.state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def reset(self) -> None:
        self.state = ConversationState()
        self.save()

    def update(self, **values: Any) -> ConversationState:
        for key, value in values.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        self.save()
        return self.state

    def context(self) -> dict[str, Any]:
        return {
            "active_task": self.state.active_task,
            "intent": self.state.intent,
            "slots": dict(self.state.slots),
            "last_question": self.state.last_question,
            "previous_tool_result": self.state.previous_tool_result,
        }
