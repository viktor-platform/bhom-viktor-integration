import asyncio
import queue
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import viktor as vkt
from agents import (
    Agent,
    ItemHelpers,
    MaxTurnsExceeded,
    Runner,
    set_default_openai_client,
    set_tracing_disabled,
)
from agents.items import MessageOutputItem, TResponseInputItem
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from agent.tools import TOOL_DISPLAY_NAMES, get_tools
from agent.types import AgentContext

PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.xml"
MAX_AGENT_TURNS = 100


viktor_llm_client = AsyncOpenAI(
    base_url=vkt.ViktorOpenAI.get_base_url(version="v1"),
    api_key=vkt.ViktorOpenAI.get_api_key(),
)

set_default_openai_client(viktor_llm_client, use_for_tracing=False)
set_tracing_disabled(True)


class WorkflowAgentRuntime:
    def __init__(self) -> None:
        self._agent: Agent[AgentContext] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._state_lock = threading.Lock()

    @staticmethod
    def _extract_call_id(raw: Any) -> str | None:
        if isinstance(raw, dict):
            value = raw.get("call_id") or raw.get("id") or raw.get("tool_call_id")
            return str(value) if value else None
        for attr in ("call_id", "id", "tool_call_id"):
            value = getattr(raw, attr, None)
            if value:
                return str(value)
        return None

    @staticmethod
    def _extract_tool_name(raw: Any) -> str:
        if isinstance(raw, dict):
            if raw.get("name"):
                return str(raw["name"])
            fn = raw.get("function")
            if isinstance(fn, dict) and fn.get("name"):
                return str(fn["name"])
            if raw.get("tool_name"):
                return str(raw["tool_name"])
        for attr in ("name", "tool_name", "function_name"):
            value = getattr(raw, attr, None)
            if value:
                return str(value)
        fn = getattr(raw, "function", None)
        if fn is not None and getattr(fn, "name", None):
            return str(fn.name)
        return "tool"

    @staticmethod
    def _normalize_stream_text(text: str) -> str:
        return " ".join(text.split()).strip()

    def _get_agent(self) -> Agent[AgentContext]:
        with self._state_lock:
            if self._agent is None:
                self._agent = Agent[AgentContext](
                    name="BHoM Revit-to-LCA Assistant",
                    model="openai.gpt-oss-120b",
                    instructions=PROMPT_PATH.read_text(encoding="utf-8"),
                    tools=get_tools(),
                )
            return self._agent

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._state_lock:
            if self._loop is not None and self._loop.is_running():
                return self._loop

            loop = asyncio.new_event_loop()
            started = threading.Event()

            def run_loop() -> None:
                asyncio.set_event_loop(loop)
                loop.call_soon(started.set)
                loop.run_forever()

            loop_thread = threading.Thread(
                target=run_loop,
                name="agent-loop",
                daemon=True,
            )
            self._loop = loop
            self._loop_thread = loop_thread
            loop_thread.start()
            if not started.wait(timeout=5):
                raise RuntimeError("Agent event loop did not start.")
            return loop

    async def _produce(
        self,
        chat_history: list[TResponseInputItem],
        *,
        context: AgentContext,
        show_tool_progress: bool,
        output_queue: queue.Queue[object],
        sentinel: object,
    ) -> None:
        call_id_to_name: dict[str, str] = {}
        pending_assistant_message: str | None = None
        streamed_text = ""
        try:
            result = Runner.run_streamed(
                self._get_agent(),
                input=chat_history,
                context=context,
                max_turns=MAX_AGENT_TURNS,
            )

            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data,
                    ResponseTextDeltaEvent,
                ):
                    if event.data.delta:
                        streamed_text += event.data.delta
                        output_queue.put(event.data.delta)
                    continue

                if not show_tool_progress or event.type != "run_item_stream_event":
                    continue

                item = event.item
                raw = getattr(item, "raw_item", None)

                if event.name == "message_output_created" and isinstance(
                    item, MessageOutputItem
                ):
                    text = ItemHelpers.text_message_output(item).strip()
                    if text and self._normalize_stream_text(
                        text
                    ) != self._normalize_stream_text(streamed_text):
                        pending_assistant_message = text
                    else:
                        pending_assistant_message = None
                    streamed_text = ""
                    continue

                if event.name == "tool_called":
                    if pending_assistant_message:
                        output_queue.put(f"\n\n{pending_assistant_message}\n\n")
                        pending_assistant_message = None
                    call_id = self._extract_call_id(raw)
                    tool_name = self._extract_tool_name(raw)
                    if call_id:
                        call_id_to_name[call_id] = tool_name
                    display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                    output_queue.put(f"\n\n> Running **{display_name}**\n")
                    continue

                if event.name == "tool_output":
                    call_id = self._extract_call_id(raw)
                    tool_name = call_id_to_name.get(call_id or "", "tool")
                    display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                    output_queue.put(f"\n> Done **{display_name}**\n\n")

        except MaxTurnsExceeded:
            output_queue.put(
                "\n\nThe agent exceeded the allowed number of turns. "
                "Try a smaller request or split the workflow into fewer tool calls.\n"
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
            output_queue.put(f"\n\n{type(exc).__name__}: {exc}\n")
        finally:
            if pending_assistant_message:
                output_queue.put(f"\n\n{pending_assistant_message}\n\n")
            output_queue.put(sentinel)

    @staticmethod
    def _stream_output(
        output_queue: queue.Queue[object],
        sentinel: object,
        on_done: Callable[[], None] | None,
    ) -> Iterator[str]:
        while True:
            item = output_queue.get()
            if item is sentinel:
                break
            yield cast(str, item)
        if on_done:
            on_done()

    def stream(
        self,
        chat_history: list[TResponseInputItem],
        *,
        context: AgentContext | None = None,
        on_done: Callable[[], None] | None = None,
        show_tool_progress: bool = True,
    ) -> Iterator[str]:
        output_queue: queue.Queue[object] = queue.Queue()
        sentinel = object()
        loop = self._ensure_loop()
        asyncio.run_coroutine_threadsafe(
            self._produce(
                chat_history,
                context=context or AgentContext(),
                show_tool_progress=show_tool_progress,
                output_queue=output_queue,
                sentinel=sentinel,
            ),
            loop,
        )
        return self._stream_output(output_queue, sentinel, on_done)

    def close(self) -> None:
        with self._state_lock:
            loop = self._loop
            loop_thread = self._loop_thread
            self._loop = None
            self._loop_thread = None

        if loop is None:
            return
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if loop_thread is not None and loop_thread is not threading.current_thread():
            loop_thread.join(timeout=5)
        if not loop.is_running() and not loop.is_closed():
            loop.close()


workflow_agent_runtime = WorkflowAgentRuntime()
