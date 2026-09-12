import json

from .schemas import ToolRequest
from .schemas import ToolSpec


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> ToolSpec:
        if not tool.name or tool.name in self._tools:
            raise ValueError(f"Tool name must be unique: {tool.name!r}")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def require(self, name: str) -> ToolSpec:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return tool

    def schemas(self) -> list[dict]:
        return [tool.public_schema() for tool in self._tools.values()]

    def parse_request(self, response: str) -> ToolRequest | None:
        candidate = (response or "").strip()
        if candidate.startswith("```") and candidate.endswith("```"):
            candidate = candidate[3:-3].strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
        try:
            payload = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        name = payload.get("tool") or payload.get("name")
        arguments = payload.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict) or self.get(name) is None:
            return None
        return ToolRequest(name, arguments)
