"""
Cursor Status API - Control the near-cursor status indicator

Shows/hides a small status pill that follows the mouse cursor.
Used to display short "thinking" updates during vision actions.
"""

from typing import Optional

from ui.visualization_api.client import get_client


def _normalize_source(source: Optional[str]) -> str:
    if isinstance(source, str) and source.strip():
        return source.strip()
    return "unknown"


def _log_cursor(channel: str, text: str, source: Optional[str] = None):
    if channel == "update":
        return
    safe_text = "" if text is None else str(text)
    src = _normalize_source(source)
    print(f"[UI_CURSOR][{src}][{channel}] {safe_text}")


async def show_cursor_status(
    text: str = "Working...",
    theme: Optional[dict] = None,
    source: Optional[str] = None,
):
    payload = {
        "command": "show_cursor_status",
        "text": text,
        "source": _normalize_source(source),
    }
    _log_cursor("show", text, source)
    if theme:
        payload["theme"] = theme
    client = await get_client()
    await client.send(payload)


async def update_cursor_status(
    text: str,
    theme: Optional[dict] = None,
    source: Optional[str] = None,
):
    payload = {
        "command": "update_cursor_status",
        "text": text,
        "source": _normalize_source(source),
    }
    _log_cursor("update", text, source)
    if theme:
        payload["theme"] = theme
    client = await get_client()
    await client.send(payload)


async def hide_cursor_status():
    payload = {
        "command": "hide_cursor_status",
    }
    client = await get_client()
    await client.send(payload)


async def set_cursor_status_position(x: int, y: int):
    payload = {
        "command": "set_cursor_status_position",
        "x": x,
        "y": y,
    }
    client = await get_client()
    await client.send(payload)
