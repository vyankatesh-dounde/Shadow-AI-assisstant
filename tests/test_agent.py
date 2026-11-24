import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from agent.agent import Agent
from agent.conversation import ConversationManager
from agent.schemas import AgentState, PermissionLevel, ToolRequest, ToolSpec
from core.brain import _cmd_place_search
from core.personality import Personality
from ai.llm import ask_ai


class AgentTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.agent = Agent(ConversationManager(root / "state.json"))
        self.agent.executor.log_file = root / "actions.jsonl"

    def tearDown(self):
        self.tempdir.cleanup()

    async def test_conversation_state_persists(self):
        self.agent.tasks.start("book_movie", "movie", {"movie": "Dune"})
        restored = ConversationManager(self.agent.conversation.state_file)

        self.assertEqual(restored.state.intent, "book_movie")
        self.assertEqual(restored.state.slots["movie"], "Dune")

    async def test_movie_slots_trigger_discovery_tool(self):
        self.agent.registry.require("search_movie_options").handler = (
            lambda **arguments: f"results for {arguments['movie']}"
        )

        async def fallback():
            return "fallback"

        replies = []
        for text in ("I want to watch a movie tonight", "Dune", "8 pm", "two"):
            replies.append(await self.agent.handle(text, fallback))

        self.assertEqual(replies[:3], [
            "Which movie?",
            "What time would you like?",
            "How many people?",
        ])
        self.assertEqual(replies[3], "results for Dune")
        self.assertEqual(self.agent.conversation.state.state, AgentState.SPEAKING)

    async def test_destructive_tool_requires_confirmation_then_can_cancel(self):
        self.agent.registry.register(ToolSpec(
            "delete_test",
            "delete a test item",
            {"item": {"type": "string"}},
            ["item"],
            PermissionLevel.DESTRUCTIVE,
            handler=lambda item: "deleted",
        ))

        result = self.agent.executor.execute(
            ToolRequest("delete_test", {"item": "demo"}),
            self.agent.conversation.state,
        )
        self.assertEqual(result.error, "confirmation_required")
        self.assertEqual(self.agent.conversation.state.state, AgentState.WAITING_CONFIRMATION)

        async def fallback():
            return "fallback"

        self.assertEqual(await self.agent.handle("cancel", fallback), "Okay, I cancelled that.")
        self.assertIsNone(self.agent.conversation.state.pending_confirmation)

    def test_real_world_actions_require_confirmation(self):
        result = self.agent.executor.execute(
            ToolRequest("book_movie", {"movie": "Dune", "time": "20:00", "people": 2}),
            self.agent.conversation.state,
        )
        self.assertEqual(result.error, "confirmation_required")
        self.assertEqual(self.agent.conversation.state.pending_confirmation["tool"], "book_movie")

    async def test_expired_confirmation_is_discarded(self):
        self.agent.executor.execute(
            ToolRequest("book_movie", {"movie": "Dune", "time": "20:00", "people": 2}),
            self.agent.conversation.state,
        )
        self.agent.conversation.state.pending_confirmation["requested_at"] = "2000-01-01T00:00:00+00:00"
        self.agent.conversation.save()

        async def fallback():
            return "fallback"

        self.assertEqual(
            await self.agent.handle("yes", fallback),
            "That confirmation expired, so I did not run the action.",
        )
        self.assertIsNone(self.agent.conversation.state.pending_confirmation)

    def test_call_book_lookup_requires_confirmation(self):
        call_book = Path(self.tempdir.name) / "call_book.json"
        call_book.write_text(json.dumps({
            "family": {"Mom": {"phone": "+1 555 0100"}},
            "hotels": {},
            "box_office": {},
        }))
        with patch("core.call_book.CALL_BOOK_FILE", call_book):
            request = self.agent._call_request("call Mom")

        result = self.agent.executor.execute(request, self.agent.conversation.state)
        self.assertEqual(result.error, "confirmation_required")
        self.assertEqual(self.agent.conversation.state.pending_confirmation["tool"], "call_contact")

    async def test_invalid_tool_arguments_are_logged(self):
        self.agent.registry.register(ToolSpec(
            "number_test",
            "accept a number",
            {"value": {"type": "number"}},
            ["value"],
            PermissionLevel.READ,
            handler=lambda value: value,
        ))

        result = self.agent.executor.execute(
            ToolRequest("number_test", {"value": "not a number"}),
            self.agent.conversation.state,
        )
        self.assertEqual(result.error, "invalid_arguments")
        record = json.loads(self.agent.executor.log_file.read_text().splitlines()[-1])
        self.assertEqual(record["error"], "invalid_arguments")
        self.assertFalse(record["success"])

    async def test_ask_ai_streams_response_chunks(self):
        chunks = []

        class FakeResponse:
            def __init__(self):
                self._payload = [
                    'data: {"choices":[{"delta":{"content":"Hello "}}]}',
                    'data: {"choices":[{"delta":{"content":"there"}}]}',
                    'data: {"choices":[{"delta":{"content":"!"}}]}',
                    "data: [DONE]",
                ]

            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                for item in self._payload:
                    yield item

        with patch("ai.llm._http_client.stream", new_callable=MagicMock) as stream_mock:
            stream_context = AsyncMock()
            stream_context.__aenter__.return_value = FakeResponse()
            stream_mock.return_value = stream_context
            async def on_chunk(chunk):
                chunks.append(chunk)

            reply = await ask_ai(
                "hello",
                Personality(),
                {},
                [],
                on_chunk=on_chunk,
            )

        self.assertEqual(reply, "Hello there!")
        self.assertEqual("".join(chunks), "Hello there!")
        self.assertEqual(
            stream_mock.call_args.args[1],
            "http://localhost:8080/v1/chat/completions",
        )
        payload = stream_mock.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "Qwen3.5-2B-Q4_K_M")
        self.assertEqual(payload["messages"][-1], {"role": "user", "content": "hello"})
        self.assertIn(
            "always reply in Marathi using Devanagari script",
            payload["messages"][0]["content"],
        )

    async def test_ask_ai_collects_stream_without_chunk_callback(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield 'data: {"choices":[{"delta":{"content":"Local "}}]}'
                yield 'data: {"choices":[{"delta":{"content":"reply"}}]}'
                yield "data: [DONE]"
        with patch("ai.llm._http_client.stream", new_callable=MagicMock) as stream_mock:
            stream_context = AsyncMock()
            stream_context.__aenter__.return_value = FakeResponse()
            stream_mock.return_value = stream_context
            reply = await ask_ai("hello", Personality(), {}, [])

        self.assertEqual(reply, "Local reply")

    async def test_structured_llm_tool_call_uses_registered_executor(self):
        self.agent.registry.register(ToolSpec(
            "safe_test",
            "run a safe test",
            {"value": {"type": "string"}},
            ["value"],
            PermissionLevel.READ,
            handler=lambda value: f"handled {value}",
        ))

        async def fallback():
            return '{"tool":"safe_test","arguments":{"value":"from llm"}}'

        self.assertEqual(await self.agent.handle("do the safe test", fallback), "handled from llm")

    def test_tool_parser_rejects_unknown_or_malformed_calls(self):
        self.assertIsNone(self.agent.registry.parse_request("not json"))
        self.assertIsNone(self.agent.registry.parse_request(
            '{"tool":"not_registered","arguments":{}}'
        ))

    def test_map_command_is_read_only_and_routed(self):
        with patch("core.brain.search_places_and_format", return_value="map results") as search:
            result = _cmd_place_search(
                "find restaurants in Delhi",
                "find restaurants in delhi",
                {},
            )

        self.assertEqual(result, "map results")
        search.assert_called_once()


if __name__ == "__main__":
    unittest.main()
