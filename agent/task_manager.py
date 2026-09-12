from typing import Any

from .conversation import ConversationManager


class TaskManager:
    def __init__(self, conversation: ConversationManager):
        self.conversation = conversation

    @property
    def state(self):
        return self.conversation.state

    def start(self, intent: str, task: str | None = None, slots: dict[str, Any] | None = None) -> None:
        self.conversation.update(
            active_task=task or intent,
            intent=intent,
            slots=slots or {},
            last_question=None,
        )

    def fill(self, values: dict[str, Any]) -> None:
        self.state.slots.update({key: value for key, value in values.items() if value is not None})
        self.conversation.save()

    def cancel(self) -> None:
        self.conversation.reset()

    def set_question(self, question: str | None) -> None:
        self.conversation.update(last_question=question)

    def missing(self, required: list[str]) -> list[str]:
        return [key for key in required if not self.state.slots.get(key)]
