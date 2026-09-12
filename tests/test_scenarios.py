import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agent.agent import Agent
from agent.conversation import ConversationManager
from agent.schemas import AgentState, PermissionLevel, ToolRequest, ToolSpec


class ConversationScenarioTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.agent = Agent(ConversationManager(root / "state.json"))
        self.agent.executor.log_file = root / "actions.jsonl"

    def tearDown(self):
        self.tempdir.cleanup()

    async def test_restaurant_continuation_and_correction(self):
        self.agent.registry.require("search_restaurant_options").handler = (
            lambda **arguments: f"restaurants for {arguments['restaurant']} at {arguments['time']}"
        )

        async def fallback():
            return "fallback"

        self.assertEqual(
            await self.agent.handle("reserve a restaurant tonight", fallback),
            "Which restaurant?",
        )
        self.assertEqual(
            await self.agent.handle("an Italian restaurant", fallback),
            "What time would you like?",
        )
        self.assertEqual(
            await self.agent.handle("actually 9 pm", fallback),
            "How many people?",
        )
        self.assertEqual(await self.agent.handle("four", fallback), "restaurants for an Italian restaurant at actually 9 pm")

    async def test_active_task_can_be_cancelled(self):
        async def fallback():
            return "fallback"

        await self.agent.handle("I want to watch a movie", fallback)
        self.assertEqual(await self.agent.handle("cancel", fallback), "Okay, I cancelled the active task.")
        self.assertIsNone(self.agent.conversation.state.active_task)
        self.assertEqual(self.agent.conversation.state.state, AgentState.IDLE)

    async def test_tool_failure_is_recoverable(self):
        def broken_tool():
            raise RuntimeError("provider offline")

        self.agent.registry.register(ToolSpec(
            "broken_test",
            "test a provider failure",
            permission=PermissionLevel.READ,
            handler=broken_tool,
        ))
        result = self.agent.executor.execute(ToolRequest("broken_test"), self.agent.conversation.state)
        self.assertFalse(result.success)
        self.assertEqual(self.agent.conversation.state.state, AgentState.ERROR)
        self.assertIn("failed", result.message)


if __name__ == "__main__":
    unittest.main()
