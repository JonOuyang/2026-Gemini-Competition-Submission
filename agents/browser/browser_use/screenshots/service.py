"""Minimal screenshot persistence service used by browser_use.agent.service."""

from __future__ import annotations

import base64
from pathlib import Path


class ScreenshotService:
    """Stores base64 screenshots to disk for history/GIF generation."""

    def __init__(self, agent_directory: str | Path):
        self.agent_directory = Path(agent_directory)
        self.screenshots_dir = self.agent_directory / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    async def store_screenshot(self, screenshot_b64: str, step: int) -> str | None:
        if not screenshot_b64:
            return None

        payload = screenshot_b64
        if "," in payload and payload.startswith("data:image"):
            payload = payload.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(payload, validate=False)
        except Exception:
            return None

        filename = f"step_{step:04d}.png"
        path = self.screenshots_dir / filename
        path.write_bytes(image_bytes)
        return str(path)
