import os
import asyncio
import time
from PIL import ImageGrab
from core.settings import set_host_and_port, set_screen_size, get_model_configs, get_screen_size

from models.models import call_gemini, store_screenshot
from agents.clovis.tools import stop_all_actions
from agents.cua_vision.tools import (
    reset_state as reset_cua_vision_state,
    request_stop as request_cua_vision_stop,
)
from ui.server import VisualizationServer


async def main():
    # Figure out open port and set it in settings.json
    settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
    host, port = set_host_and_port(settings_path)

    # Figure out dimensions of the user's screen and set it in settings.json.
    # Fallback to configured size if capture is unavailable at startup.
    try:
        screen_width, screen_height = await asyncio.wait_for(
            asyncio.to_thread(lambda: ImageGrab.grab().size),
            timeout=2.0,
        )
    except Exception as exc:
        try:
            screen_width, screen_height = get_screen_size(settings_path)
        except Exception:
            screen_width, screen_height = (1920, 1080)
        print(
            f"Screen capture unavailable at startup ({type(exc).__name__}: {exc}). "
            f"Using configured size {screen_width}x{screen_height}."
        )
    set_screen_size(screen_width, screen_height)

    # Retrieve model configs from settings
    rapid_response_model, clovis_model = get_model_configs(settings_path)
    print(f"Models loaded - Rapid: {rapid_response_model}, CLOVIS: {clovis_model}")

    current_task = None
    task_lock = asyncio.Lock()
    last_overlay_text = ""
    last_overlay_ts = 0.0

    async def stop_all():
        nonlocal current_task
        print("Stop requested: cancelling active tasks.")
        request_cua_vision_stop()
        async with task_lock:
            task = current_task
        if task and not task.done():
            task.cancel()
        stop_all_actions()
        reset_cua_vision_state()

    async def _run_overlay_task(text: str):
        nonlocal current_task
        try:
            await call_gemini(text, rapid_response_model, clovis_model)
        except asyncio.CancelledError:
            print("Active task cancelled.")
        except Exception as exc:
            print(f"Active task failed: {exc}")
        finally:
            async with task_lock:
                if current_task is asyncio.current_task():
                    current_task = None

    async def handle_overlay_input(text):
        nonlocal current_task, last_overlay_text, last_overlay_ts
        text = text.strip()
        if not text:
            return
        now = time.monotonic()
        if text == last_overlay_text and (now - last_overlay_ts) < 1.2:
            print(f"Overlay input ignored (duplicate within 1.2s): {text}")
            return

        last_overlay_text = text
        last_overlay_ts = now
        async with task_lock:
            if current_task and not current_task.done():
                print("Overlay input ignored (task already running).")
                return
            print(f"Overlay input: {text}")
            task = asyncio.create_task(_run_overlay_task(text))
            current_task = task

    server = VisualizationServer(
        host=host,
        port=port,
        on_overlay_input=handle_overlay_input,
        on_capture_screenshot=store_screenshot,
        on_stop_all=stop_all
    )
    await server.start()
    print(f"Visualization server listening at ws://{host}:{port}")
    print("Waiting for overlay client connection...")
    await server.wait_for_client()
    print("Overlay client connected.")

    await server.wait_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        # _clear_screen()
        pass
