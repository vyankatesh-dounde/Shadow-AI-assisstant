from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class PermissionLevel(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    FINANCIAL = "FINANCIAL"


class AgentState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SEARCHING = "SEARCHING"
    EXECUTING = "EXECUTING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    permission: PermissionLevel = PermissionLevel.READ
    requires_confirmation: bool = False
    handler: Optional[Callable[..., Any]] = field(default=None, repr=False, compare=False)

    def public_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "required": self.required,
            "permission": self.permission.value,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class ToolRequest:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    success: bool
    message: str
    data: Any = None
    error: Optional[str] = None


@dataclass
class ConversationState:
    active_task: Optional[str] = None
    intent: Optional[str] = None
    slots: dict[str, Any] = field(default_factory=dict)
    pending_confirmation: Optional[dict[str, Any]] = None
    previous_tool_result: Any = None
    last_question: Optional[str] = None
    state: AgentState = AgentState.IDLE

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ConversationState":
        state = value.get("state", AgentState.IDLE)
        try:
            state = AgentState(state)
        except ValueError:
            state = AgentState.IDLE
        return cls(
            active_task=value.get("active_task"),
            intent=value.get("intent"),
            slots=value.get("slots") or {},
            pending_confirmation=value.get("pending_confirmation"),
            previous_tool_result=value.get("previous_tool_result"),
            last_question=value.get("last_question"),
            state=state,
        )
