"""
Interactive Test: Status Bubble Completion Flow

This test uses mocked messages (no model calls) to validate:
1. Task runs in top status bubble
2. Completion shows "Task done" briefly, then expands with final response
3. Clicking expanded status bubble restores center input + under-bar response
4. Dismiss button (x) hides the expanded status bubble

Usage:
    python tests/test_status_bubble_completion_interactive.py
"""

import asyncio
import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from ui.server import VisualizationServer
from ui.visualization_api.clear_screen import _clear_screen
from ui.visualization_api.status_bubble import (
    show_status_bubble,
    update_status_bubble,
    complete_status_bubble,
    show_command_overlay,
)

LIGHT_STATUS_THEME = {
    "statusBg": "rgba(245, 248, 252, 0.96)",
    "statusBorder": "rgba(15, 20, 30, 0.1)",
    "statusText": "rgba(15, 20, 30, 0.94)",
    "statusShimmer": "rgba(60, 120, 220, 0.55)",
    "statusCheck": "rgba(60, 120, 220, 0.9)",
}


async def _run_mock_task(final_response: str):
    await show_command_overlay()
    await asyncio.sleep(0.8)

    await show_status_bubble("Running mocked agent...", theme=LIGHT_STATUS_THEME)
    await asyncio.sleep(1.0)
    await update_status_bubble("Gathering context...", theme=LIGHT_STATUS_THEME)
    await asyncio.sleep(1.0)
    await update_status_bubble("Executing mocked steps...", theme=LIGHT_STATUS_THEME)
    await asyncio.sleep(1.0)

    await complete_status_bubble(
        final_response,
        done_text="Task done",
        delay_ms=2000,
        theme=LIGHT_STATUS_THEME,
    )


async def run_test():
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    host = "127.0.0.1"
    port = 8765

    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    settings["host"] = host
    settings["port"] = port
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=4)

    server = VisualizationServer(host=host, port=port)
    await server.start()
    print("[completion_interactive] Waiting for client connection on ws://127.0.0.1:8765...")
    await server.wait_for_client()
    print("[completion_interactive] Client connected!")

    try:
        print("[completion_interactive] Phase 1: click expanded status bubble body.")
        await _run_mock_task(
            "Mocked CLI confirmation: wrote 2 files and finished without errors."
        )
        print("[completion_interactive] When expanded, click the status bubble body.")
        print("[completion_interactive] Expected: center command input is restored and response appears underneath it.")
        await asyncio.sleep(14)

        print("[completion_interactive] Phase 2: click the X dismiss button.")
        await _run_mock_task(
            "Mocked browser confirmation: extracted 5 results from the page."
        )
        print("[completion_interactive] When expanded, click the X on the right.")
        print("[completion_interactive] Expected: status bubble dismisses.")
        await asyncio.sleep(14)
    finally:
        await _clear_screen()
        await server.stop()
        print("[completion_interactive] Test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\n[completion_interactive] Interrupted by user.")
