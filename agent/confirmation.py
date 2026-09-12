from datetime import datetime, timezone

from .schemas import ConversationState, ToolRequest


CONFIRMATION_TTL_SECONDS = 300


CONFIRMATIONS = {"yes", "y", "confirm", "confirmed", "do it", "go ahead", "sure", "okay", "ok"}
CANCELLATIONS = {"no", "n", "cancel", "stop", " never mind", "never mind"}


def is_confirmation(text: str) -> bool:
    return text.casefold().strip() in CONFIRMATIONS


def is_cancellation(text: str) -> bool:
    return text.casefold().strip() in CANCELLATIONS


def request_confirmation(state: ConversationState, request: ToolRequest, prompt: str) -> None:
    state.pending_confirmation = {
        "tool": request.name,
        "arguments": request.arguments,
        "prompt": prompt,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }


def confirmation_expired(state: ConversationState) -> bool:
    pending = state.pending_confirmation
    if not pending:
        return False
    try:
        requested = datetime.fromisoformat(pending["requested_at"])
    except (KeyError, TypeError, ValueError):
        return True
    age = (datetime.now(timezone.utc) - requested).total_seconds()
    return age > CONFIRMATION_TTL_SECONDS


def clear_confirmation(state: ConversationState) -> None:
    state.pending_confirmation = None
