"""
Legacy CUA Vision element locator.

This module preserves the old two-call click-localization behavior so it can be
used as an internal fallback when direct single-call actions fail repeatedly.
"""

import asyncio
import os
import random

from PIL import ImageGrab
import pygetwindow as gw

try:
    from google import genai
    from google.genai import types
except ImportError:
    print('Google Gemini dependencies have not been installed')

from agents.cua_vision.keyboard import (
    move_cursor,
    click_left_click,
    click_double_left_click,
    click_right_click,
)
from ui.visualization_api.cursor_status import (
    show_cursor_status,
    update_cursor_status,
    hide_cursor_status,
)


def _dispatch_now(coro):
    """Schedule a coroutine on the current loop (or run it directly)."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            asyncio.run(coro)
        except RuntimeError:
            pass


def _capture_active_window():
    """Capture the currently active window, falling back to full screen."""
    try:
        bbox = _get_active_window_bbox()
        if bbox:
            return ImageGrab.grab(bbox=bbox)
    except Exception as e:
        print(f"Error capturing active window for legacy locator: {e}")

    return ImageGrab.grab()


def _get_active_window_title() -> str:
    """Get the active window title for prompt context."""
    try:
        return gw.getActiveWindowTitle() or "Unknown"
    except Exception:
        return "Unknown"


def _get_active_window_bbox():
    """
    Return active window bounds as (left, top, right, bottom), or None.

    Handles environments where getActiveWindow() may return a string title.
    """
    try:
        window = gw.getActiveWindow()
    except Exception:
        return None

    def _bounds_from_window(win):
        required = ("left", "top", "width", "height")
        if not all(hasattr(win, key) for key in required):
            return None
        try:
            left = int(win.left)
            top = int(win.top)
            width = int(win.width)
            height = int(win.height)
        except Exception:
            return None
        if width <= 0 or height <= 0:
            return None
        return (left, top, left + width, top + height)

    bbox = _bounds_from_window(window)
    if bbox:
        return bbox

    if isinstance(window, str) and window:
        try:
            candidates = gw.getWindowsWithTitle(window)
        except Exception:
            return None
        for candidate in candidates:
            bbox = _bounds_from_window(candidate)
            if bbox:
                return bbox

    return None


def legacy_find_and_click_element(
    type_of_click: str,
    element_description: str,
    should_stop=None,
):
    """
    Legacy behavior: use a second model call to localize an element, then click.

    Args:
        type_of_click: One of "left click", "double left click", "right click"
        element_description: Human description of the intended target.
    """
    status_messages = [
        f"Searching for {element_description}...",
        f"Scanning screen for {element_description}...",
        f"Looking for the best match: {element_description}...",
        f"Locating clickable target: {element_description}...",
    ]
    initial_status = random.choice(status_messages)
    _dispatch_now(show_cursor_status(initial_status, source="cua_vision"))
    print(f"[LegacyLocator] Searching for: {element_description}")

    try:
        if callable(should_stop) and should_stop():
            print("[LegacyLocator] Stop requested before fallback lookup; aborting.")
            return False

        screenshot = _capture_active_window()
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        _dispatch_now(update_cursor_status(initial_status, source="cua_vision"))

        config = types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=64,
            max_output_tokens=30,
        )

        model_prompt = f"""
This image is a screenshot of {_get_active_window_title()} - an application that contains many interactive elements.

Give me a very in depth description of everything you see in this image. Include all icons that you may see such as search bars or home buttons, colors, position relative to one another and the screen, etc.
Describe what you suspect the purpose of every single element in the image may be responsible for.

Now use this description to assist your response, but no matter what do not reveal any of this description unless prompted to do so.
Please keep in mind that only one element can be pressed. Your bounding box should only contain at most one clickable element.
Return a bounding box for the {element_description}. Do NOT output any words:
[ymin, xmin, ymax, xmax]
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[screenshot, model_prompt],
            config=config,
        )

        _dispatch_now(update_cursor_status("Target located. Moving cursor...", source="cua_vision"))
        temp_list = response.text.strip()
        temp_list = temp_list[1:-1]
        coords = [float(item) for item in temp_list.split(", ")]

        coords[0] = coords[0] / 1000 * screenshot.size[1]
        coords[1] = coords[1] / 1000 * screenshot.size[0]
        coords[2] = coords[2] / 1000 * screenshot.size[1]
        coords[3] = coords[3] / 1000 * screenshot.size[0]

        if callable(should_stop) and should_stop():
            print("[LegacyLocator] Stop requested before fallback click; aborting.")
            return False

        bbox = _get_active_window_bbox()
        offset_x = bbox[0] if bbox else 0
        offset_y = bbox[1] if bbox else 0
        center_x = (coords[3] - coords[1]) / 2 + coords[1] + offset_x
        center_y = (coords[2] - coords[0]) / 2 + coords[0] + offset_y

        move_cursor(center_x, center_y, duration=0.2)

        if type_of_click == "left click":
            click_left_click()
        elif type_of_click == "double left click":
            click_double_left_click()
        elif type_of_click == "right click":
            click_right_click()
        else:
            raise ValueError(f"Unsupported click type: {type_of_click}")
        return True
    finally:
        _dispatch_now(hide_cursor_status())
