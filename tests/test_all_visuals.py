"""
Test: All Visual Suites (Box -> Points -> CUA CLI -> CUA Vision)

Runs a single end-to-end sequence using one visualization server instance.
Between each suite, shows a brief on-screen popup label and clears the overlay.

Usage:
    python tests/test_all_visuals.py
"""

import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from core.settings import get_screen_size, set_host_and_port
from ui.server import VisualizationServer
from ui.visualization_api.clear_screen import _clear_screen
from ui.visualization_api.create_text import _create_text
from ui.visualization_api.destroy_text import _destroy_text
from agents.clovis.tools import (
    create_text,
    create_text_for_box,
    draw_bounding_box,
    draw_pointer_to_object,
    stop_all_actions,
)
from tests.test_status_bubble_cua_cli import simulate_cua_cli_agent
from tests.test_status_bubble_cua_vision import simulate_cua_vision_agent


async def _show_stage_popup(label: str, duration: float = 1.2):
    width, height = get_screen_size()
    center_x = int((width or 1470) * 0.5)
    center_y = int((height or 956) * 0.2)
    popup_id = "all_visuals_stage_popup"

    await _create_text(
        center_x,
        center_y,
        label,
        popup_id,
        24,
        "SF Pro Display",
        "center",
        "middle",
    )
    await asyncio.sleep(duration)
    await _destroy_text(popup_id)


async def _run_box_sequence():
    # Matches box_test visuals without creating another server loop.
    draw_bounding_box(
        0.0,
        200,
        200,
        800,
        600,
        stroke=None,
        stroke_width=10,
        auto_contrast=True,
        box_id="all_box_1",
    )

    draw_bounding_box(
        0.4,
        520,
        700,
        880,
        980,
        stroke="rgba(45, 123, 255, 0.95)",
        stroke_width=6,
        opacity=0.7,
        box_id="all_box_2",
    )

    draw_bounding_box(
        0.7,
        120,
        780,
        420,
        1120,
        stroke="#82D7FF",
        stroke_width=5,
        opacity=0.82,
        box_id="all_box_3",
    )

    draw_bounding_box(
        1.0,
        620,
        120,
        900,
        420,
        stroke="#4B9DFF",
        stroke_width=7,
        opacity=0.78,
        box_id="all_box_4",
    )

    create_text(
        0.6,
        150,
        550,
        "In the hush of morning light,\nA quiet thought takes flight.",
        font_size=20,
    )

    box = {"x": 200, "y": 160, "width": 400, "height": 600}
    create_text_for_box(0.8, box, "Box label", position="top")

    await asyncio.sleep(3.6)


async def _run_points_sequence():
    # Matches points_test visuals without creating another server loop.
    draw_pointer_to_object(
        time=0.2,
        x_pos=260,
        y_pos=220,
        text="Point A",
        text_x=392,
        text_y=160,
        point_id="all_point_1",
        ring_color="#66B7FF",
    )

    draw_pointer_to_object(
        time=0.5,
        x_pos=720,
        y_pos=280,
        text="Point B",
        text_x=888,
        text_y=220,
        point_id="all_point_2",
        ring_color="#82D7FF",
    )

    draw_pointer_to_object(
        time=0.8,
        x_pos=480,
        y_pos=520,
        text="Point C",
        text_x=612,
        text_y=628,
        point_id="all_point_3",
        ring_color="#4B9DFF",
    )

    draw_pointer_to_object(
        time=1.1,
        x_pos=980,
        y_pos=430,
        text="Point D",
        text_x=1088,
        text_y=370,
        point_id="all_point_4",
        ring_color="#66B7FF",
    )

    draw_pointer_to_object(
        time=1.4,
        x_pos=340,
        y_pos=700,
        text="Point E",
        text_x=470,
        text_y=760,
        point_id="all_point_5",
        ring_color="#9AC7FF",
    )

    await asyncio.sleep(4.2)


async def _clear_between_steps():
    stop_all_actions()
    await _clear_screen()
    await asyncio.sleep(0.35)


async def run_test_all_visuals():
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    host, port = set_host_and_port(settings_path)

    server = VisualizationServer(host=host, port=port)
    await server.start()
    print("[test_all_visuals] Waiting for client connection...")
    await server.wait_for_client()
    print("[test_all_visuals] Client connected!")

    try:
        await _clear_between_steps()

        print("[test_all_visuals] Running box_test sequence...")
        await _show_stage_popup("Running: box_test")
        await _run_box_sequence()
        await _clear_between_steps()

        print("[test_all_visuals] Running points_test sequence...")
        await _show_stage_popup("Running: points_test")
        await _run_points_sequence()
        await _clear_between_steps()

        print("[test_all_visuals] Running cua_cli sequence...")
        await _show_stage_popup("Running: test_status_bubble_cua_cli")
        await simulate_cua_cli_agent()
        await asyncio.sleep(1.8)
        await _clear_between_steps()

        print("[test_all_visuals] Running cua_vision sequence...")
        await _show_stage_popup("Running: test_status_bubble_cua_vision")
        await simulate_cua_vision_agent()
        await asyncio.sleep(2.0)
        await _clear_between_steps()

        print("[test_all_visuals] All sequences completed.")
        await _show_stage_popup("All visual tests complete", duration=1.0)
    finally:
        stop_all_actions()
        await _clear_screen()
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_test_all_visuals())
    except KeyboardInterrupt:
        print("\n[test_all_visuals] Interrupted by user.")
