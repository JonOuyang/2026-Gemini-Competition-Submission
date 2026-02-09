"""
Test: Status Bubble - CUA Vision Agent

This test triggers the status bubble with simulated CUA Vision agent status updates.
Does NOT call the actual LLM - just demonstrates the status bubble UI flow.

Usage:
    python tests/test_status_bubble_cua_vision.py
"""

import asyncio
import os
import random
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

import pyautogui

from core.settings import set_host_and_port
from ui.server import VisualizationServer
from ui.visualization_api.status_bubble import (
    show_status_bubble,
    update_status_bubble,
    hide_status_bubble,
)
from ui.visualization_api.cursor_status import (
    show_cursor_status,
    update_cursor_status,
    hide_cursor_status,
    set_cursor_status_position,
)


async def simulate_cua_vision_agent():
    """
    Simulates mouse movement with near-cursor thinking and status bubble updates.
    """
    screen_width, screen_height = pyautogui.size()

    # Keep clicks comfortably away from screen edges.
    margin = 140
    min_x, max_x = margin, max(margin + 1, screen_width - margin)
    min_y, max_y = margin, max(margin + 1, screen_height - margin)

    points = [
        (random.randint(min_x, max_x), random.randint(min_y, max_y))
        for _ in range(3)
    ]

    cursor_messages = [
        "Searching for next button...",
        "Checking likely click target...",
        "Scanning visible controls...",
        "Finding the best match...",
        "Locating actionable element...",
    ]

    await show_status_bubble("Starting vision scan...")
    await show_cursor_status(random.choice(cursor_messages))

    for idx, (target_x, target_y) in enumerate(points, start=1):
        await update_status_bubble(f"Moving to point {idx}...")

        pyautogui.moveTo(target_x, target_y, duration=0.225)
        next_cursor_msg = random.choice(cursor_messages)
        await update_cursor_status(next_cursor_msg)
        await asyncio.sleep(0.6)

    await update_status_bubble("Task complete")
    await asyncio.sleep(0.6)
    await hide_cursor_status()
    await hide_status_bubble(delay=1000)


async def run_test():
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    host, port = set_host_and_port(settings_path)

    server = VisualizationServer(host=host, port=port)
    await server.start()
    print("[test_status_bubble_cua_vision] Waiting for client connection...")
    await server.wait_for_client()
    print("[test_status_bubble_cua_vision] Client connected!")

    print("[test_status_bubble_cua_vision] Starting CUA Vision agent simulation...")
    await simulate_cua_vision_agent()
    print("[test_status_bubble_cua_vision] Simulation complete!")

    # Keep server running for a moment to see the final state
    await asyncio.sleep(2)
    print("[test_status_bubble_cua_vision] Test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\n[test_status_bubble_cua_vision] Interrupted by user.")
