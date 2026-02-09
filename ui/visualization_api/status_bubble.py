"""
Status Bubble API - Control the agent status indicator

Shows/hides the status bubble at the top of the screen.
Used to display agent activity like "Opening file...", "Searching online..."
"""

from typing import Optional

from ui.visualization_api.client import get_client


def _normalize_source(source: Optional[str]) -> str:
    if isinstance(source, str) and source.strip():
        return source.strip()
    return "unknown"


def _log_status(channel: str, text: str, source: Optional[str] = None):
    if channel == "update":
        return
    safe_text = "" if text is None else str(text)
    src = _normalize_source(source)
    print(f"[UI_STATUS][{src}][{channel}] {safe_text}")


async def show_status_bubble(
    text: str = "Working...",
    theme: Optional[dict] = None,
    source: Optional[str] = None,
):
    """
    Show the status bubble with initial text.

    Args:
        text (str): The status text to display (default: "Working...")
    """
    payload = {
        "command": "show_status_bubble",
        "text": text,
    }
    _log_status("show", text, source)
    payload["source"] = _normalize_source(source)
    if theme:
        payload["theme"] = theme
    client = await get_client()
    await client.send(payload)


async def update_status_bubble(
    text: str,
    theme: Optional[dict] = None,
    source: Optional[str] = None,
):
    """
    Update the status bubble text.

    Args:
        text (str): The new status text to display
    """
    payload = {
        "command": "update_status_bubble",
        "text": text,
    }
    _log_status("update", text, source)
    payload["source"] = _normalize_source(source)
    if theme:
        payload["theme"] = theme
    client = await get_client()
    await client.send(payload)


async def hide_status_bubble(delay: int = 0):
    """
    Hide the status bubble.

    Args:
        delay (int): Optional delay in milliseconds before hiding (default: 0)
    """
    payload = {
        "command": "hide_status_bubble",
        "delay": delay,
    }
    client = await get_client()
    await client.send(payload)


async def complete_status_bubble(
    response_text: str,
    done_text: str = "Task done",
    delay_ms: int = 2000,
    theme: Optional[dict] = None,
    source: Optional[str] = None,
):
    """
    Complete the status flow with delayed final response expansion.

    Args:
        response_text (str): Final response to show in expanded status bubble
        done_text (str): Interim completion text (default: "Task done")
        delay_ms (int): Delay before expansion in milliseconds (default: 2000)
    """
    payload = {
        "command": "complete_status_bubble",
        "responseText": response_text,
        "doneText": done_text,
        "delayMs": delay_ms,
    }
    _log_status("complete_done", done_text, source)
    _log_status("complete_response", response_text, source)
    payload["source"] = _normalize_source(source)
    if theme:
        payload["theme"] = theme
    client = await get_client()
    await client.send(payload)


async def show_command_overlay():
    """Show the centered command overlay (test/debug helper)."""
    client = await get_client()
    await client.send({"command": "show_command_overlay"})
