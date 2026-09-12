import re
from typing import Any, Awaitable, Callable

from core.maps_search import search_places_and_format
from core.desktop_control import close_app, open_app, open_website
from core.call_book import call_contact, find_contact
from core.file_indexer import build_index, open_indexed
from core.reminders import add_reminder, delete_reminder, list_reminders
from core.real_world_tools import (
    book_movie,
    place_food_order,
    reserve_restaurant,
    search_food_options,
    search_movie_options,
    search_restaurant_options,
)
from core.system_status import get_status
from core.web_search import search_and_format
from .confirmation import confirmation_expired, is_cancellation, is_confirmation
from .conversation import ConversationManager
from .planner import Planner
from .schemas import AgentState, PermissionLevel, ToolSpec
from .schemas import ToolRequest
from .task_manager import TaskManager
from .tool_executor import ToolExecutor
from .tool_registry import ToolRegistry


def _create_reminder(text: str, trigger_time: float) -> str:
    add_reminder(text, trigger_time)
    return f"Reminder created: {text}"


def _delete_reminder(reminder_id: str) -> str:
    delete_reminder(reminder_id)
    return f"Reminder deleted: {reminder_id}"


class Agent:
    def __init__(self, conversation: ConversationManager | None = None):
        self.conversation = conversation or ConversationManager()
        self.tasks = TaskManager(self.conversation)
        self.planner = Planner()
        self.registry = ToolRegistry()
        self._register_tools()
        self.executor = ToolExecutor(self.registry)

    def _register_tools(self) -> None:
        tools = [
            ToolSpec(
                "search_maps",
                "find restaurants or movie theaters and available contact details",
                {"query": {"type": "string"}, "location": {"type": "string"}},
                ["query"], PermissionLevel.READ, handler=search_places_and_format,
            ),
            ToolSpec(
                "search_web",
                "search the web for current information",
                {"query": {"type": "string"}}, ["query"],
                PermissionLevel.READ, handler=search_and_format,
            ),
            ToolSpec(
                "system_status",
                "read CPU, memory, battery, uptime, and active-window status",
                permission=PermissionLevel.READ, handler=get_status,
            ),
            ToolSpec(
                "list_reminders",
                "list pending reminders",
                permission=PermissionLevel.READ, handler=list_reminders,
            ),
            ToolSpec(
                "index_files",
                "index local files for later lookup",
                permission=PermissionLevel.WRITE, handler=build_index,
            ),
            ToolSpec(
                "open_app",
                "open an installed application",
                {"app_name": {"type": "string"}}, ["app_name"],
                PermissionLevel.WRITE, handler=open_app,
            ),
            ToolSpec(
                "open_file",
                "open a file or folder from the indexed file list",
                {"query": {"type": "string"}}, ["query"],
                PermissionLevel.WRITE, handler=open_indexed,
            ),
            ToolSpec(
                "open_website",
                "open a website search in the browser",
                {"query": {"type": "string"}}, ["query"],
                PermissionLevel.EXTERNAL_ACTION, requires_confirmation=True,
                handler=open_website,
            ),
            ToolSpec(
                "create_reminder",
                "create a reminder",
                {"text": {"type": "string"}, "trigger_time": {"type": "number"}},
                ["text", "trigger_time"], PermissionLevel.WRITE, handler=_create_reminder,
            ),
            ToolSpec(
                "delete_reminder",
                "delete a reminder",
                {"reminder_id": {"type": "string"}}, ["reminder_id"],
                PermissionLevel.DESTRUCTIVE, handler=_delete_reminder,
            ),
            ToolSpec(
                "close_app",
                "force-close an application",
                {"name": {"type": "string"}}, ["name"],
                PermissionLevel.DESTRUCTIVE, handler=close_app,
            ),
            ToolSpec(
                "call_contact",
                "open a phone call to a saved contact",
                {"name": {"type": "string"}, "phone": {"type": "string"}},
                ["name", "phone"], PermissionLevel.EXTERNAL_ACTION,
                requires_confirmation=True, handler=call_contact,
            ),
            ToolSpec(
                "search_movie_options",
                "find current movie showtimes and options",
                {"movie": {"type": "string"}, "date": {"type": "string"}, "time": {"type": "string"}, "location": {"type": "string"}},
                ["movie"], PermissionLevel.READ, handler=search_movie_options,
            ),
            ToolSpec(
                "search_restaurant_options",
                "find restaurants and available contact details",
                {"restaurant": {"type": "string"}, "date": {"type": "string"}, "time": {"type": "string"}, "location": {"type": "string"}},
                ["restaurant"], PermissionLevel.READ, handler=search_restaurant_options,
            ),
            ToolSpec(
                "search_food_options",
                "find menus and food delivery options",
                {"restaurant": {"type": "string"}, "items": {"type": "string"}, "location": {"type": "string"}},
                ["restaurant"], PermissionLevel.READ, handler=search_food_options,
            ),
            ToolSpec(
                "book_movie",
                "book a selected movie showtime",
                {"movie": {"type": "string"}, "time": {"type": "string"}, "people": {"type": "number"}},
                ["movie", "time", "people"], PermissionLevel.EXTERNAL_ACTION,
                requires_confirmation=True, handler=book_movie,
            ),
            ToolSpec(
                "reserve_restaurant",
                "reserve a selected restaurant table",
                {"restaurant": {"type": "string"}, "date": {"type": "string"}, "time": {"type": "string"}, "people": {"type": "number"}},
                ["restaurant", "date", "time", "people"], PermissionLevel.EXTERNAL_ACTION,
                requires_confirmation=True, handler=reserve_restaurant,
            ),
            ToolSpec(
                "place_food_order",
                "place a food order and charge the user",
                {"restaurant": {"type": "string"}, "items": {"type": "string"}},
                ["restaurant", "items"], PermissionLevel.FINANCIAL,
                requires_confirmation=True, handler=place_food_order,
            ),
        ]
        for tool in tools:
            self.registry.register(tool)

    def _follow_up_slots(self, text: str) -> dict[str, Any]:
        question = self.conversation.state.last_question
        if not question:
            return {}
        if question == "Which movie?":
            return {"movie": text.strip()}
        if question == "Which restaurant?":
            return {"restaurant": text.strip()}
        if question == "What would you like to order?":
            return {"items": text.strip()}
        if question == "How many people?":
            match = re.search(r"\d+", text)
            if match:
                return {"people": int(match.group())}
            words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            for word, value in words.items():
                if re.search(rf"\b{word}\b", text.casefold()):
                    return {"people": value}
            return {}
        if question == "What time would you like?":
            return {"time": text.strip()}
        if question == "What date should I use?":
            return {"date": text.strip()}
        return {}

    def context(self) -> dict[str, Any]:
        return self.conversation.context()

    def _map_request(self, text: str) -> ToolRequest | None:
        lower = text.casefold()
        if any(word in lower for word in ("book", "reserve", "order")):
            return None
        if not any(word in lower for word in ("find", "search", "look for", "where is", "near me", "nearby")):
            return None
        if "restaurant" in lower:
            query = "restaurants"
        elif any(word in lower for word in ("movie theater", "cinema", "movie theatre")):
            query = "movie theaters"
        else:
            return None
        location = ""
        if " in " in lower:
            location = text[lower.index(" in ") + 4:].strip()
        return ToolRequest("search_maps", {"query": query, "location": location})

    def _call_request(self, text: str) -> ToolRequest | None:
        match = re.match(r"^\s*(?:call|dial)\s+(.+?)\s*$", text, re.I)
        if not match:
            return None
        target = match.group(1)
        lower = target.casefold()
        category = ""
        if "hotel" in lower:
            category = "hotels"
        elif "box office" in lower or "boxoffice" in lower:
            category = "box_office"
        contact = find_contact(target, category)
        if not contact:
            return ToolRequest("call_contact", {"name": target, "phone": ""})
        return ToolRequest("call_contact", {"name": contact["name"], "phone": contact["phone"]})

    def _discovery_request(self, intent: str, slots: dict[str, Any]) -> ToolRequest | None:
        tool_by_intent = {
            "book_movie": "search_movie_options",
            "reserve_restaurant": "search_restaurant_options",
            "order_food": "search_food_options",
        }
        tool = tool_by_intent.get(intent)
        if not tool:
            return None
        arguments = dict(slots)
        arguments.setdefault("location", "")
        return ToolRequest(tool, arguments)

    async def handle(self, text: str, fallback: Callable[[], Awaitable[str]]) -> str:
        state = self.conversation.state
        clean = text.casefold().strip()

        if state.pending_confirmation:
            if confirmation_expired(state):
                self.conversation.reset()
                return "That confirmation expired, so I did not run the action."
            if is_confirmation(clean):
                request = state.pending_confirmation
                result = self.executor.execute(
                    ToolRequest(request["tool"], request.get("arguments", {})),
                    state,
                    confirmed=True,
                )
                next_state = AgentState.SPEAKING if result.success else AgentState.ERROR
                self.conversation.update(previous_tool_result=result.message, state=next_state)
                return result.message
            if is_cancellation(clean):
                self.conversation.reset()
                return "Okay, I cancelled that."

        if clean in {"cancel", "stop", "never mind", "forget it"} and state.active_task:
            self.tasks.cancel()
            return "Okay, I cancelled the active task."

        call_request = self._call_request(text)
        if call_request:
            if not call_request.arguments.get("phone"):
                return f"I couldn't find {call_request.arguments['name']} in call_book.json."
            result = self.executor.execute(call_request, state)
            next_state = AgentState.SPEAKING if result.success else (
                AgentState.WAITING_CONFIRMATION
                if result.error == "confirmation_required"
                else AgentState.ERROR
            )
            self.conversation.update(previous_tool_result=result.message, state=next_state)
            return result.message

        map_request = self._map_request(text)
        if map_request:
            result = self.executor.execute(map_request, state)
            next_state = AgentState.SPEAKING if result.success else AgentState.ERROR
            self.conversation.update(previous_tool_result=result.message, state=next_state)
            return result.message

        plan = self.planner.plan(text)
        if state.active_task and state.last_question:
            self.tasks.fill(self._follow_up_slots(text))
            plan = self.planner.plan(f"{state.active_task} {text}")
            plan.intent = state.intent
            plan.required_slots = {
                "book_movie": ["movie", "time", "people"],
                "reserve_restaurant": ["restaurant", "date", "time", "people"],
                "order_food": ["restaurant", "items"],
            }.get(state.intent, [])

        if plan.intent:
            if state.intent != plan.intent:
                self.tasks.start(plan.intent, plan.task, plan.slots)
            else:
                self.tasks.fill(plan.slots)
            missing = self.tasks.missing(plan.required_slots)
            if missing:
                labels = {"movie": "Which movie?", "time": "What time would you like?", "people": "How many people?", "restaurant": "Which restaurant?", "date": "What date should I use?", "items": "What would you like to order?"}
                question = labels[missing[0]]
                self.tasks.set_question(question)
                self.conversation.update(state=AgentState.LISTENING)
                return question
            discovery = self._discovery_request(plan.intent, self.conversation.state.slots)
            if discovery:
                self.tasks.set_question(None)
                result = self.executor.execute(discovery, state)
                next_state = AgentState.SPEAKING if result.success else AgentState.ERROR
                self.conversation.update(previous_tool_result=result.message, state=next_state)
                return result.message

        self.conversation.update(state=AgentState.THINKING)
        reply = await fallback()
        tool_request = self.registry.parse_request(reply)
        if tool_request:
            result = self.executor.execute(tool_request, state)
            next_state = AgentState.SPEAKING if result.success else (
                AgentState.WAITING_CONFIRMATION
                if result.error == "confirmation_required"
                else AgentState.ERROR
            )
            self.conversation.update(previous_tool_result=result.message, state=next_state)
            return result.message
        self.conversation.update(previous_tool_result=None, state=AgentState.SPEAKING)
        return reply
