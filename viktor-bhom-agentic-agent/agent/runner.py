import asyncio
import queue
import threading
from collections.abc import Iterator
from pathlib import Path

import viktor as vkt
from agents import Agent, Runner, set_default_openai_client, set_tracing_disabled
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from agent.tools import TOOL_DISPLAY_NAMES, get_tools
from agent.types import AgentContext

PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.xml"
client = AsyncOpenAI(
    base_url=vkt.ViktorOpenAI.get_base_url(version="v1"),
    api_key=vkt.ViktorOpenAI.get_api_key(),
)
set_default_openai_client(client, use_for_tracing=False)
set_tracing_disabled(True)


class WorkflowAgentRuntime:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def _event_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop and self._loop.is_running():
            return self._loop
        loop = asyncio.new_event_loop()
        started = threading.Event()

        def run() -> None:
            asyncio.set_event_loop(loop)
            started.set()
            loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True, name="bhom-agent-loop")
        self._thread.start()
        started.wait(timeout=5)
        self._loop = loop
        return loop

    async def _produce(
        self,
        messages: list[dict[str, str]],
        context: AgentContext,
        output: queue.Queue[object],
        done: object,
    ) -> None:
        try:
            agent = Agent[AgentContext](
                name="BHoM LCA workflow assistant",
                model="openai.gpt-oss-120b",
                instructions=PROMPT_PATH.read_text(encoding="utf-8"),
                tools=get_tools(),
            )
            result = Runner.run_streamed(
                agent, input=messages, context=context, max_turns=12
            )
            async for event in result.stream_events():
                if (
                    event.type == "raw_response_event"
                    and isinstance(event.data, ResponseTextDeltaEvent)
                    and event.data.delta
                ):
                    output.put(event.data.delta)
                if (
                    event.type == "run_item_stream_event"
                    and event.name == "tool_called"
                ):
                    raw = getattr(event.item, "raw_item", None)
                    tool_name = getattr(raw, "name", None) or getattr(
                        raw, "tool_name", None
                    )
                    if tool_name:
                        output.put(
                            f"\n\n> Running **{TOOL_DISPLAY_NAMES.get(str(tool_name), tool_name)}**\n\n"
                        )
        except (ConnectionError, RuntimeError, ValueError, OSError) as error:
            output.put(f"\n\n{type(error).__name__}: {error}\n")
        finally:
            output.put(done)

    def stream(
        self, messages: list[dict[str, str]], *, context: AgentContext
    ) -> Iterator[str]:
        output: queue.Queue[object] = queue.Queue()
        done = object()
        asyncio.run_coroutine_threadsafe(
            self._produce(messages, context, output, done), self._event_loop()
        )
        while True:
            item = output.get()
            if item is done:
                return
            yield str(item)


workflow_agent_runtime = WorkflowAgentRuntime()
