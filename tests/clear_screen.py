import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from agents.clovis.tools import clear_screen
from core.settings import set_host_and_port
from ui.server import VisualizationServer


async def main():
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    host, port = set_host_and_port(settings_path)

    server = VisualizationServer(host=host, port=port)
    await server.start()
    await server.wait_for_client()

    clear_screen(0.0)
    await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
