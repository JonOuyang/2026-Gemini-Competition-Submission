"""
Test: Status Bubble - CUA CLI Agent

This test triggers the status bubble with simulated CUA CLI agent status updates.
Does NOT call the actual LLM - just demonstrates the status bubble UI flow.

Usage:
    python tests/test_status_bubble_cua_cli.py
"""

import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from core.settings import set_host_and_port
from ui.server import VisualizationServer
from ui.visualization_api.status_bubble import (
    show_status_bubble,
    update_status_bubble,
    hide_status_bubble,
)


async def simulate_cua_cli_agent():
    """
    Simulates the status updates a CUA CLI agent would produce.
    """
    status_messages = [
        "Opening terminal...",
        "Reading file structure...",
        "Executing: ls -la",
        "Processing output...",
        "Writing to config.json...",
        "Running npm install...",
        "Build successful",
        "Task complete",
    ]

    # Let server-side auto contrast decide the correct mode from the first frame.
    await show_status_bubble(status_messages[0])
    await asyncio.sleep(1.2)

    for msg in status_messages[1:]:
        await update_status_bubble(msg)
        await asyncio.sleep(1.2)

    # Hide after showing "Task complete" briefly
    await hide_status_bubble(delay=1000)


async def run_test():
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    host, port = set_host_and_port(settings_path)

    server = VisualizationServer(host=host, port=port)
    await server.start()
    print("[test_status_bubble_cua_cli] Waiting for client connection...")
    await server.wait_for_client()
    print("[test_status_bubble_cua_cli] Client connected!")

    print("[test_status_bubble_cua_cli] Starting CUA CLI agent simulation...")
    await simulate_cua_cli_agent()
    print("[test_status_bubble_cua_cli] Simulation complete!")

    # Keep server running for a moment to see the final state
    await asyncio.sleep(2)
    print("[test_status_bubble_cua_cli] Test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\n[test_status_bubble_cua_cli] Interrupted by user.")
