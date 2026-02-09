import asyncio
import os
import sys
from typing import Optional, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from core.settings import set_host_and_port
from ui.server import VisualizationServer
from agents.clovis.tools import (
    clear_screen,
    create_text,
    create_text_for_box,
    draw_bounding_box,
)

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None


def _find_light_point(step: int = 80, threshold: int = 200) -> Optional[Tuple[int, int]]:
    if ImageGrab is None:
        return None
    try:
        image = ImageGrab.grab().convert("RGB")
    except Exception:
        return None
    width, height = image.size
    if width <= 0 or height <= 0:
        return None
    for y in range(0, height, step):
        for x in range(0, width, step):
            r, g, b = image.getpixel((x, y))
            luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
            if luminance >= threshold:
                return x, y
    return None


async def run_overlay_smoke_test():
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    host, port = set_host_and_port(settings_path)

    server = VisualizationServer(host=host, port=port)
    await server.start()
    await server.wait_for_client()

    print("beginning overlay smoke test")

    clear_screen(0.0)
    await asyncio.sleep(0.2)

    # Box 1 uses auto-contrast on the dark desktop (should be light stroke).
    draw_bounding_box(
        0.0,
        200,
        200,
        800,
        600,
        stroke=None,
        stroke_width=10,
        auto_contrast=True,
        box_id="smoke_box_1",
    )
    await asyncio.sleep(0.2)

    # Box 2 forces the dark-mode stroke (how it should look on light backgrounds).
    draw_bounding_box(
        0.4,
        520,
        700,
        880,
        980,
        stroke="rgba(45, 123, 255, 0.95)",
        stroke_width=6,
        opacity=0.7,
        box_id="smoke_box_2",
    )
    await asyncio.sleep(0.2)

    draw_bounding_box(
        0.7,
        120,
        780,
        420,
        1120,
        stroke="#82D7FF",
        stroke_width=5,
        opacity=0.82,
        box_id="smoke_box_3",
    )
    await asyncio.sleep(0.2)

    draw_bounding_box(
        1.0,
        620,
        120,
        900,
        420,
        stroke="#4B9DFF",
        stroke_width=7,
        opacity=0.78,
        box_id="smoke_box_4",
    )
    await asyncio.sleep(0.2)

    create_text(
        0.6,
        150,
        550,
        "In the hush of morning light,\nA quiet thought takes flight.",
        font_size=20,
    )
    await asyncio.sleep(0.2)

    box = {"x": 200, "y": 160, "width": 400, "height": 600}
    create_text_for_box(0.8, box, "Box label", position="top")
    await asyncio.sleep(0.2)

    clear_screen(11.0)
    await asyncio.sleep(0.2)
    print("cleared the screen")
    await server.wait_forever()


if __name__ == "__main__":
    try:
        asyncio.run(run_overlay_smoke_test())
    except KeyboardInterrupt:
        pass
