"""
Primary single-call execution engine for CUA Vision.

This module handles per-step model calls where the model returns both the next
action and user-visible status text in one response.
"""

import asyncio
import json
import os

from google.api_core.exceptions import InternalServerError

from integrations.audio import tts_speak
from agents.cua_vision.prompts import VISION_AGENT_SYSTEM_PROMPT
from ui.visualization_api.cursor_status import (
    show_cursor_status,
    update_cursor_status,
    hide_cursor_status,
)
from ui.visualization_api.status_bubble import (
    show_status_bubble,
    update_status_bubble,
    hide_status_bubble,
)
from agents.cua_vision.tools import (
    capture_active_window,
    get_active_window_title,
    get_memory,
    execute_tool_call,
    run_legacy_locator_fallback,
    is_stop_requested,
    save_go_to_element_debug_snapshot,
)

CLICK_TOOL_TO_TYPE = {
    "click_left_click": "left click",
    "click_double_left_click": "double left click",
    "click_right_click": "right click",
}
CLICK_TYPE_TO_TOOL = {
    "left click": "click_left_click",
    "double left click": "click_double_left_click",
    "right click": "click_right_click",
}
POSITIONING_TOOLS = {"go_to_element", "crop_and_search"}
AUTO_CLICK_AFTER_REPEAT_POSITIONING_THRESHOLD = 2
POSITION_BUCKET_SIZE = 40
CLICK_CYCLE_LOOP_STOP_THRESHOLD = 4
DEFAULT_ACTION_SETTLE_DELAY_SECONDS = 1.0
POST_BATCH_DELAY_SECONDS = 0.05

THINKING_MESSAGES = [
    "Analyzing screen...",
    "Reviewing visible UI elements...",
    "Planning the next action...",
    "Checking the safest interaction...",
]

TOOL_METADATA_KEYS = {"status_text", "target_description"}


def _is_truthy_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class DebugStopAfterFirstGoTo(RuntimeError):
    """Raised when debug mode intentionally stops after first go_to_element."""


class SingleCallVisionEngine:
    """Runs the main task loop for VisionAgent using one model call per step."""

    def __init__(self, agent):
        self.agent = agent
        self.consecutive_failures = 0
        self.max_failures_before_fallback = 3
        self.last_action_signature = None
        self.repeated_action_count = 0
        self.last_click_context = None
        self.last_target_description = None
        self._pending_position_signature = None
        self._last_click_cycle_signature = None
        self._repeated_click_cycle_count = 0
        self._status_visible = False
        self._last_status_text = None
        self._thinking_index = 0
        self._debug_snapshot_taken = False
        self._action_settle_delay_seconds = DEFAULT_ACTION_SETTLE_DELAY_SECONDS
        self.debug_stop_after_first_goto = _is_truthy_env(
            os.getenv("CUA_VISION_DEBUG_STOP_AFTER_FIRST_GOTO", "0")
        )

    async def run(self, task: str):
        """Execute the task until completion or unrecoverable failure."""
        try:
            self._raise_if_stopped()
            while True:
                self._raise_if_stopped()
                response = await self._generate_step_response(task)
                self._raise_if_stopped()
                function_calls = self._extract_function_calls(response)

                if not function_calls:
                    should_continue = await self._handle_no_function_call(task)
                    if should_continue:
                        continue
                    return

                function_calls = self._normalize_function_call_batch(function_calls)
                if len(function_calls) > 1:
                    print(f"[VisionAgent] Executing {len(function_calls)} tool calls from one model response.")

                done = await self._handle_function_calls(task, function_calls)
                if done:
                    return

                self._raise_if_stopped()
                await asyncio.sleep(POST_BATCH_DELAY_SECONDS)
        finally:
            await self._hide_statuses(delay_ms=400)

    async def _generate_step_response(self, task: str):
        self._raise_if_stopped()
        active_window = get_active_window_title()
        memory_text, _ = get_memory()

        model_prompt = self._build_model_prompt(task, active_window, memory_text)
        screenshot = capture_active_window()

        thinking_text = THINKING_MESSAGES[self._thinking_index % len(THINKING_MESSAGES)]
        self._thinking_index += 1
        await self._set_status(thinking_text)

        model_task = asyncio.create_task(
            self.agent.client.aio.models.generate_content(
                model=self.agent.model_name,
                contents=[model_prompt, screenshot],
                config=self.agent.analysis_config,
            )
        )
        try:
            while True:
                self._raise_if_stopped()
                done, _ = await asyncio.wait({model_task}, timeout=0.15)
                if done:
                    response = model_task.result()
                    self.agent.retries = 0
                    return response
        except asyncio.CancelledError:
            model_task.cancel()
            raise
        except InternalServerError as e:
            self.agent.retries += 1
            if self.agent.retries < self.agent.max_retries:
                await self._set_status(
                    f"Model error. Retrying ({self.agent.retries}/{self.agent.max_retries})..."
                )
                await asyncio.sleep(1)
                self._raise_if_stopped()
                return await self._generate_step_response(task)
            raise e

    def _build_model_prompt(self, task: str, active_window: str, memory_text):
        memory_json = json.dumps(memory_text)
        return f"""
{VISION_AGENT_SYSTEM_PROMPT}

You are controlling the user's active application window.
Application: {active_window}
User goal: {task}
Stored memory: {memory_json}

First, analyze the screenshot in detail privately.
Then decide the best NEXT action for this exact screen.

IMPORTANT:
- You may call ONE function, or a TWO-function position+click sequence.
- If you call TWO functions, they must be:
  1) `go_to_element` or `crop_and_search`
  2) then one click tool (`click_left_click`/`click_double_left_click`/`click_right_click`)
- Never emit more than TWO function calls in one response.
- Prefer direct action tools (position/click/type/hotkeys) over descriptive selectors.
- Click actions are two-step:
  1) Position cursor with `go_to_element` (or `crop_and_search` when uncertain)
  2) Then click, either immediately in the same response or in the next step
- Do NOT pass x/y coordinates to click tools.
- Do not call `go_to_element`/`crop_and_search` repeatedly for the same target on unchanged screen.
- After positioning for a target, your next step should usually be the click itself.
- `crop_and_search` is OPTIONAL and should only be used when helpful.
- If the target location is clear, use `go_to_element`.
- If the target is tiny/crowded or click confidence is low, use `crop_and_search`.
- For `crop_and_search`, provide a best-effort bounding box [ymin, xmin, ymax, xmax] (0-1000 coords).
- Do not pass a single point to `go_to_element` or `crop_and_search`; pass a box around the likely target.
- The crop tool adds padding internally, so your box can be approximate.
- For every non-terminal action function call, include a concise `status_text` argument.
  Example: "Searching for Next button..." or "Typing into email field..."
- For click tools, also include `target_description` (short target label) for fallback.
- Only interact with elements you can currently see.
- Before choosing an action, check if the user goal is already satisfied on this screen.
- When the task is fully complete, call `task_is_complete` and do not call any other function.
- App-launch tasks on macOS should prefer keyboard flow:
  1) `press_ctrl_hotkey(key="space")` (maps to Command+Space on macOS)
  2) `type_string(string="<app name>", submit=true)`
  3) continue the rest of the task after app opens
- Avoid clicking tiny menu bar Spotlight icons when shortcut launch is available.
- Do not stop immediately after opening an app if the user asked for more actions.
"""

    def _extract_function_calls(self, response):
        try:
            parts = response.candidates[0].content.parts
        except Exception:
            return []
        return [part.function_call for part in parts if part.function_call]

    async def _handle_no_function_call(self, task: str) -> bool:
        self._raise_if_stopped()
        self.consecutive_failures += 1
        self.agent.retries += 1

        if self.consecutive_failures >= self.max_failures_before_fallback:
            fallback_success = await self._attempt_fallback(task, None, None)
            if fallback_success:
                self.agent.retries = 0
                self.consecutive_failures = 0
                return True

        if self.agent.retries < self.agent.max_retries:
            await self._set_status(
                f"No action selected. Retrying ({self.agent.retries}/{self.agent.max_retries})..."
            )
            return True

        tts_speak("I couldn't determine the next action. Please try again.")
        raise RuntimeError("Max retries reached without function call")

    def _normalize_function_call_batch(self, function_calls: list):
        """Allow controlled multi-call sequences per model response."""
        if len(function_calls) <= 1:
            return function_calls

        first = function_calls[0]
        if first.name == "task_is_complete":
            return [first]

        if len(function_calls) >= 2:
            second = function_calls[1]
            if first.name in POSITIONING_TOOLS and second.name in CLICK_TOOL_TO_TYPE:
                if len(function_calls) >= 3 and function_calls[2].name == "task_is_complete":
                    if len(function_calls) > 3:
                        print(
                            "[VisionAgent] Received more than 3 function calls; "
                            "dropping extras after position+click+complete."
                        )
                    return function_calls[:3]
                if len(function_calls) > 2:
                    print(
                        "[VisionAgent] Received more than 2 function calls; "
                        "dropping extras after position+click."
                    )
                return function_calls[:2]

            if first.name in CLICK_TOOL_TO_TYPE and second.name == "task_is_complete":
                if len(function_calls) > 2:
                    print(
                        "[VisionAgent] Received more than 2 function calls; "
                        "dropping extras after click+complete."
                    )
                return function_calls[:2]

        print(
            "[VisionAgent] Multi-call sequence is unsupported; "
            "executing only the first call."
        )
        return [first]

    async def _handle_function_calls(self, task: str, function_calls: list) -> bool:
        """Execute one to three controlled tool calls from a single model response."""
        has_explicit_click = any(call.name in CLICK_TOOL_TO_TYPE for call in function_calls)
        for function_call in function_calls:
            done = await self._handle_function_call(
                task,
                function_call,
                allow_positioning_autoclick=not has_explicit_click,
            )
            if done:
                return True
            self._raise_if_stopped()
        return False

    async def _handle_function_call(
        self,
        task: str,
        function_call,
        allow_positioning_autoclick: bool = True,
    ) -> bool:
        self._raise_if_stopped()
        name = function_call.name
        args = dict(function_call.args or {})

        status_text = args.get("status_text") or self._default_status_text(name)
        if status_text:
            await self._set_status(status_text)

        click_type = self._resolve_click_type(name, args)
        signature = self._action_signature(name, args)
        if signature == self.last_action_signature:
            self.repeated_action_count += 1
        else:
            self.last_action_signature = signature
            self.repeated_action_count = 1

        if click_type and self.repeated_action_count >= self.max_failures_before_fallback:
            fallback_success = await self._attempt_fallback(task, click_type, args)
            if fallback_success:
                self.consecutive_failures = 0
                self.repeated_action_count = 0
                return False

        if (
            allow_positioning_autoclick
            and
            name in POSITIONING_TOOLS
            and self.repeated_action_count >= AUTO_CLICK_AFTER_REPEAT_POSITIONING_THRESHOLD
        ):
            auto_click_type = self._infer_click_type(task, args)
            auto_click_tool = CLICK_TYPE_TO_TOOL[auto_click_type]
            target = self._resolve_target_description(task, args)
            await self._set_status(f"Position repeated. Executing {auto_click_type} on {target}...")
            execute_tool_call(auto_click_tool, {"target_description": target})
            self.last_target_description = target
            self.last_click_context = {
                "type_of_click": auto_click_type,
                "target_description": target,
            }
            self.last_action_signature = None
            self.repeated_action_count = 0
            self.consecutive_failures = 0
            print(
                "[VisionAgent] Auto-click before repeated positioning: "
                f"{auto_click_type} on {target}"
            )
            await self._wait_for_ui_settle()
            return False

        print(f"[VisionAgent] Function: {name}")
        print(f"[VisionAgent] Arguments: {args}")

        try:
            self._raise_if_stopped()
            if name in {"crop_and_search", "go_to_element"}:
                # These tools can do blocking model work; run them off-loop.
                await asyncio.to_thread(execute_tool_call, name, args)
            else:
                execute_tool_call(name, args)
            self.consecutive_failures = 0

            if name in POSITIONING_TOOLS:
                self.last_target_description = self._resolve_target_description(task, args)

            if name == "go_to_element":
                await self._maybe_debug_stop_after_first_goto(task, args)

            if click_type:
                resolved_target = self._resolve_target_description(task, args)
                self.last_target_description = resolved_target
                self.last_click_context = {
                    "type_of_click": click_type,
                    "target_description": resolved_target,
                }

            if name in {"tts_speak", "task_is_complete"}:
                await self._set_status("Task complete")
                await self._hide_statuses(delay_ms=700)
                return True

            if self._register_action_and_detect_click_loop(task, name, signature, click_type):
                target = self._resolve_target_description(task, args)
                await self._set_status("Task appears complete. Stopping repeated clicks.")
                print(
                    "[VisionAgent] Detected repeated position+click loop "
                    f"on {target}. Stopping to avoid infinite retries."
                )
                await self._hide_statuses(delay_ms=700)
                return True

            await self._wait_for_ui_settle()
            return False
        except Exception as e:
            if isinstance(e, DebugStopAfterFirstGoTo):
                raise
            print(f"[VisionAgent] Tool execution failed: {e}")
            self.consecutive_failures += 1

            if click_type and self.consecutive_failures >= self.max_failures_before_fallback:
                fallback_success = await self._attempt_fallback(task, click_type, args)
                if fallback_success:
                    self.consecutive_failures = 0
                    self.repeated_action_count = 0
                    return False

            if self.agent.retries < self.agent.max_retries:
                self.agent.retries += 1
                await self._set_status(
                    f"Action failed. Retrying ({self.agent.retries}/{self.agent.max_retries})..."
                )
                return False

            raise

    async def _maybe_debug_stop_after_first_goto(self, task: str, args: dict):
        """Optional debugging: save bbox overlay and stop after first go_to_element."""
        if not self.debug_stop_after_first_goto or self._debug_snapshot_taken:
            return

        required = ("ymin", "xmin", "ymax", "xmax")
        if not all(key in args for key in required):
            return

        target = self._resolve_target_description(task, args)
        try:
            snapshot_path = save_go_to_element_debug_snapshot(
                ymin=float(args["ymin"]),
                xmin=float(args["xmin"]),
                ymax=float(args["ymax"]),
                xmax=float(args["xmax"]),
                target_description=target,
            )
        except Exception as e:
            snapshot_path = f"<failed to save snapshot: {e}>"

        self._debug_snapshot_taken = True
        await self._set_status("Debug snapshot saved. Stopping after first positioning step.")
        print(f"[VisionAgent][Debug] go_to_element snapshot: {snapshot_path}")
        raise DebugStopAfterFirstGoTo(
            "Debug stop after first go_to_element. "
            f"Snapshot: {snapshot_path}"
        )

    def _infer_click_type(self, task: str, args: dict) -> str:
        """Infer click type from task/metadata when auto-clicking after positioning loops."""
        pieces = [
            args.get("status_text"),
            args.get("target_description"),
            task,
        ]
        haystack = " ".join(str(piece).lower() for piece in pieces if piece)
        if "double click" in haystack or "double-click" in haystack:
            return "double left click"
        if "right click" in haystack or "right-click" in haystack or "context menu" in haystack:
            return "right click"
        return "left click"

    def _to_norm_0_1000(self, value) -> float | None:
        """Normalize supported coordinate formats into 0-1000 space."""
        try:
            val = float(value)
        except Exception:
            return None

        if 0.0 <= val <= 1.0:
            return val * 1000.0
        if 0.0 <= val <= 1000.0:
            return val
        # If already pixel coordinates, keep as-is; bucketing still works heuristically.
        return val

    def _position_bucket(self, args: dict) -> tuple[int, int] | None:
        """Create coarse center buckets so small bbox jitter counts as repetition."""
        ymin = self._to_norm_0_1000(args.get("ymin"))
        xmin = self._to_norm_0_1000(args.get("xmin"))
        ymax = self._to_norm_0_1000(args.get("ymax"))
        xmax = self._to_norm_0_1000(args.get("xmax"))
        if None in {ymin, xmin, ymax, xmax}:
            return None

        center_x = (xmin + xmax) / 2.0
        center_y = (ymin + ymax) / 2.0
        bucket_x = int(center_x // POSITION_BUCKET_SIZE)
        bucket_y = int(center_y // POSITION_BUCKET_SIZE)
        return (bucket_x, bucket_y)

    def _action_signature(self, name: str, args: dict) -> tuple:
        filtered = {k: v for k, v in args.items() if k not in TOOL_METADATA_KEYS}
        if name in CLICK_TOOL_TO_TYPE and "target_description" not in filtered and self.last_target_description:
            filtered["target_description"] = self.last_target_description
        if name in POSITIONING_TOOLS:
            bucket = self._position_bucket(filtered)
            if bucket is not None:
                # Deliberately ignore target_description text to survive label jitter.
                return (name, ("bucket", bucket[0], bucket[1]))
        return (name, tuple(sorted(filtered.items())))

    def _resolve_click_type(self, tool_name: str, args: dict) -> str | None:
        if tool_name in CLICK_TOOL_TO_TYPE:
            return CLICK_TOOL_TO_TYPE[tool_name]

        return None

    @staticmethod
    def _task_expects_repeated_clicks(task: str) -> bool:
        text = (task or "").lower()
        markers = [
            "times",
            "repeatedly",
            "keep clicking",
            "click again",
            "double click multiple",
            "spam click",
            "until",
            "every",
            "loop",
        ]
        return any(marker in text for marker in markers)

    def _register_action_and_detect_click_loop(
        self,
        task: str,
        name: str,
        signature: tuple,
        click_type: str | None,
    ) -> bool:
        """
        Detect alternating position+click loops (A,B,A,B...) that can evade
        immediate-repeat checks and lead to infinite interaction cycles.
        """
        if name in POSITIONING_TOOLS:
            self._pending_position_signature = signature
            return False

        if click_type:
            if self._pending_position_signature is None:
                return False

            cycle_signature = (self._pending_position_signature, signature)
            if cycle_signature == self._last_click_cycle_signature:
                self._repeated_click_cycle_count += 1
            else:
                self._last_click_cycle_signature = cycle_signature
                self._repeated_click_cycle_count = 1

            if (
                self._repeated_click_cycle_count >= CLICK_CYCLE_LOOP_STOP_THRESHOLD
                and not self._task_expects_repeated_clicks(task)
            ):
                return True
            return False

        # Non click/position actions reset this specific loop detector.
        self._pending_position_signature = None
        self._last_click_cycle_signature = None
        self._repeated_click_cycle_count = 0
        return False

    async def _attempt_fallback(self, task: str, click_type: str | None, args: dict | None) -> bool:
        self._raise_if_stopped()
        context = None

        if click_type and args is not None:
            context = {
                "type_of_click": click_type,
                "target_description": self._resolve_target_description(task, args),
            }
        elif self.last_click_context:
            context = self.last_click_context

        if not context:
            return False

        target = context.get("target_description")
        click_type = context.get("type_of_click")
        if not target or not click_type:
            return False

        await self._set_status(f"{target} is uncertain. Using precision fallback...")
        self._raise_if_stopped()
        success = run_legacy_locator_fallback(click_type, target)

        if success:
            await self._set_status(f"Fallback located {target}.")
            return True

        return False

    def _resolve_target_description(self, task: str, args: dict) -> str:
        target = args.get("target_description")
        if isinstance(target, str) and target.strip():
            return target.strip()

        status_text = args.get("status_text")
        if isinstance(status_text, str) and status_text.strip():
            normalized = status_text.strip().rstrip(".")
            prefixes = [
                "searching for ",
                "looking for ",
                "locating ",
                "clicking ",
                "opening ",
                "selecting ",
            ]
            lower = normalized.lower()
            for prefix in prefixes:
                if lower.startswith(prefix):
                    candidate = normalized[len(prefix):].strip()
                    if candidate:
                        return candidate
            return normalized

        if isinstance(self.last_target_description, str) and self.last_target_description.strip():
            return self.last_target_description.strip()

        return f"best target for task: {task}"

    def _default_status_text(self, tool_name: str) -> str:
        if tool_name == "type_string":
            return "Typing..."
        if tool_name in {"press_ctrl_hotkey", "press_alt_hotkey"}:
            return "Using shortcut..."
        if tool_name == "go_to_element":
            return "Positioning cursor to target..."
        if tool_name in CLICK_TOOL_TO_TYPE:
            return "Clicking target..."
        if tool_name == "crop_and_search":
            return "Zooming in for a precision click..."
        if tool_name == "tts_speak":
            return "Preparing response..."
        if tool_name == "task_is_complete":
            return "Task complete"
        return "Working..."

    async def _set_status(self, text: str):
        if text == self._last_status_text:
            return

        if not self._status_visible:
            await self._safe_ui_call(
                show_status_bubble(text, source="cua_vision"),
                "show_status_bubble",
            )
            await self._safe_ui_call(
                show_cursor_status(text, source="cua_vision"),
                "show_cursor_status",
            )
            self._status_visible = True
            self._last_status_text = text
            return

        await self._safe_ui_call(
            update_status_bubble(text, source="cua_vision"),
            "update_status_bubble",
        )
        await self._safe_ui_call(
            update_cursor_status(text, source="cua_vision"),
            "update_cursor_status",
        )
        self._last_status_text = text

    async def _hide_statuses(self, delay_ms: int = 0):
        if not self._status_visible:
            return

        await self._safe_ui_call(hide_cursor_status(), "hide_cursor_status")
        await self._safe_ui_call(hide_status_bubble(delay=delay_ms), "hide_status_bubble")
        self._status_visible = False
        self._last_status_text = None

    async def _safe_ui_call(self, coro, label: str):
        """Best-effort UI calls: visualization failures must not block task execution."""
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[VisionAgent] UI call failed ({label}): {e}")

    async def _wait_for_ui_settle(self):
        """Pause briefly after each successful action so UI state can update."""
        delay = float(self._action_settle_delay_seconds)
        if delay <= 0:
            return
        self._raise_if_stopped()
        await asyncio.sleep(delay)

    def _raise_if_stopped(self):
        if is_stop_requested():
            raise asyncio.CancelledError("Stop requested by user")
