import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .confirmation import clear_confirmation, request_confirmation
from .schemas import AgentState, PermissionLevel, ToolRequest, ToolResult
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, log_file: Path | None = None):
        self.registry = registry
        root = Path(__file__).resolve().parent.parent
        self.log_file = log_file or root / "memory" / "action_log.jsonl"
        self.log_file.parent.mkdir(exist_ok=True)

    def _log(self, request: ToolRequest, result: ToolResult, confirmed: bool) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": request.name,
            "arguments": request.arguments,
            "permission": self.registry.get(request.name).permission.value if self.registry.get(request.name) else None,
            "confirmed": confirmed,
            "success": result.success,
            "result": result.message,
            "error": result.error,
        }
        with self.log_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def execute(self, request: ToolRequest, state, confirmed: bool = False) -> ToolResult:
        tool = self.registry.get(request.name)
        if tool is None:
            result = ToolResult(False, f"Unknown tool: {request.name}", error="unknown_tool")
            state.state = AgentState.ERROR
            self._log(request, result, confirmed)
            return result

        missing = [
            field for field in tool.required
            if field not in request.arguments or request.arguments[field] in (None, "")
        ]
        if missing:
            result = ToolResult(False, f"Missing required arguments: {', '.join(missing)}", error="invalid_arguments")
            state.state = AgentState.ERROR
            self._log(request, result, confirmed)
            return result

        invalid = []
        for name, schema in tool.parameters.items():
            if name not in request.arguments or not isinstance(schema, dict):
                continue
            expected = schema.get("type")
            value = request.arguments[name]
            valid = (
                expected == "string" and isinstance(value, str)
                or expected == "number" and isinstance(value, (int, float)) and not isinstance(value, bool)
                or expected == "boolean" and isinstance(value, bool)
            )
            if expected and not valid:
                invalid.append(f"{name} ({expected})")
        if invalid:
            result = ToolResult(False, f"Invalid argument types: {', '.join(invalid)}", error="invalid_arguments")
            state.state = AgentState.ERROR
            self._log(request, result, confirmed)
            return result

        consequential = {
            PermissionLevel.DESTRUCTIVE,
            PermissionLevel.EXTERNAL_ACTION,
            PermissionLevel.FINANCIAL,
        }
        if (tool.requires_confirmation or tool.permission in consequential) and not confirmed:
            request_confirmation(state, request, f"Please confirm: {tool.description}.")
            state.state = AgentState.WAITING_CONFIRMATION
            result = ToolResult(False, f"Confirmation required for {tool.name}.", error="confirmation_required")
            self._log(request, result, False)
            return result

        if tool.handler is None:
            result = ToolResult(False, f"Tool {tool.name} has no implementation yet.", error="not_implemented")
            state.state = AgentState.ERROR
            self._log(request, result, confirmed)
            return result

        try:
            value = tool.handler(**request.arguments)
            result = ToolResult(True, str(value), data=value)
        except Exception as exc:
            logger.exception("Tool execution failed: %s", request.name)
            result = ToolResult(False, f"Tool {request.name} failed.", error=str(exc))
            state.state = AgentState.ERROR
        clear_confirmation(state)
        self._log(request, result, confirmed)
        return result
