import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from core.settings import set_host_and_port
from ui.server import VisualizationServer
from agents.clovis.tools import clear_screen, draw_pointer_to_object


async def run_points_test():
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    host, port = set_host_and_port(settings_path)

    server = VisualizationServer(host=host, port=port)
    await server.start()
    await server.wait_for_client()

    print("beginning points test")

    clear_screen(0.0)
    await asyncio.sleep(0.1)

    # New simplified API: dot + text + line all in one call
    draw_pointer_to_object(
        time=0.2,
        x_pos=260,
        y_pos=220,
        text="Point A",
        text_x=392,
        text_y=160,
        point_id="point_1",
        ring_color="#66B7FF",
    )

    draw_pointer_to_object(
        time=0.5,
        x_pos=720,
        y_pos=280,
        text="Point B",
        text_x=888,
        text_y=220,
        point_id="point_2",
        ring_color="#82D7FF",
    )

    draw_pointer_to_object(
        time=0.8,
        x_pos=480,
        y_pos=520,
        text="Point C",
        text_x=612,
        text_y=628,
        point_id="point_3",
        ring_color="#4B9DFF",
    )

    draw_pointer_to_object(
        time=1.1,
        x_pos=980,
        y_pos=430,
        text="Point D",
        text_x=1088,
        text_y=370,
        point_id="point_4",
        ring_color="#66B7FF",
    )

    draw_pointer_to_object(
        time=1.4,
        x_pos=340,
        y_pos=700,
        text="Point E",
        text_x=470,
        text_y=760,
        point_id="point_5",
        ring_color="#9AC7FF",
    )

    clear_screen(5.0)
    await server.wait_forever()


if __name__ == "__main__":
    try:
        asyncio.run(run_points_test())
    except KeyboardInterrupt:
        pass
