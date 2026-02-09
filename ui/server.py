import asyncio
import json
import time
from typing import Optional, Tuple

import websockets
from websockets.exceptions import ConnectionClosed
from core.settings import get_screen_size, set_screen_size

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None
try:
    import pyautogui
except Exception:
    pyautogui = None


class VisualizationServer:
    DARK_LUMINANCE_THRESHOLD = 112
    INVERTED_PANEL_DARK_THRESHOLD = 45
    STATUS_INVERTED_PANEL_DARK_THRESHOLD = 132

    def __init__(self, host="127.0.0.1", port=8765, on_overlay_input=None, on_capture_screenshot=None, on_stop_all=None):
        self.host = host
        self.port = port
        self.clients = set()
        self.boxes = {}
        self.texts = {}
        self.dots = {}
        self._server = None
        self.on_overlay_input = on_overlay_input
        self.on_capture_screenshot = on_capture_screenshot
        self.on_stop_all = on_stop_all
        self._last_screenshot = None
        self._last_screenshot_rgb = None
        self._last_capture_backend = "none"
        self._last_cursor_pos = (0, 0)
        self._last_dark_sample = False
        self._last_theme_log_ts = 0.0
        self._active_status_theme = None
        self._seen_overlay_request_ids = {}
        self._last_overlay_text = ""
        self._last_overlay_ts = 0.0

    def _store_screenshot(self, screenshot) -> None:
        self._last_screenshot = screenshot
        self._last_screenshot_rgb = None
        if screenshot is None:
            return
        try:
            self._last_screenshot_rgb = screenshot.convert("RGB")
        except Exception:
            self._last_screenshot_rgb = None

    def _is_likely_invalid_capture(self, image_rgb) -> bool:
        if image_rgb is None:
            return True
        width, height = image_rgb.size
        if width <= 0 or height <= 0:
            return True

        # Sparse sampling: if everything is near-black, this is likely a bad capture path.
        dark_like = 0
        total = 0
        for y in range(0, height, max(1, height // 6)):
            for x in range(0, width, max(1, width // 6)):
                try:
                    r, g, b = image_rgb.getpixel((x, y))
                except Exception:
                    continue
                total += 1
                if r <= 4 and g <= 4 and b <= 4:
                    dark_like += 1

        if total == 0:
            return True
        return (dark_like / total) >= 0.9

    def _get_screenshot_rgb(self):
        if self._last_screenshot_rgb is not None:
            self._last_capture_backend = "cache"
            return self._last_screenshot_rgb
        if self._last_screenshot is not None:
            self._store_screenshot(self._last_screenshot)
            self._last_capture_backend = "cache"
            return self._last_screenshot_rgb

        screenshot_rgb = None
        if ImageGrab is not None:
            try:
                screenshot_rgb = ImageGrab.grab().convert("RGB")
                self._last_capture_backend = "imagegrab"
            except Exception:
                screenshot_rgb = None

        # Fall back when PIL capture is unavailable or likely invalid (e.g., all black).
        if (screenshot_rgb is None or self._is_likely_invalid_capture(screenshot_rgb)) and pyautogui is not None:
            try:
                screenshot_rgb = pyautogui.screenshot().convert("RGB")
                self._last_capture_backend = "pyautogui"
            except Exception:
                pass

        if screenshot_rgb is None:
            self._last_capture_backend = "none"
            return None

        self._last_screenshot_rgb = screenshot_rgb
        return self._last_screenshot_rgb

    def _get_palette(self, prefer_light_text: bool) -> dict:
        if prefer_light_text:
            return {
                "mode": "light-on-dark",
                "accent": "rgba(160, 200, 255, 0.85)",
                "boxStroke": "rgba(102, 183, 255, 0.95)",
                "text": "rgba(242, 245, 248, 0.96)",
                "label": "rgba(255, 255, 255, 0.5)",
                "thinking": "rgba(210, 215, 224, 0.85)",
                "panelBg": "rgba(14, 14, 18, 0.9)",
                "panelBorder": "rgba(255, 255, 255, 0.12)",
                "meta": "rgba(255, 255, 255, 0.7)",
                "divider": "rgba(255, 255, 255, 0.75)",
                "shimmer": "rgba(255, 255, 255, 1)",
                "statusBg": "rgba(4, 5, 7, 0.96)",
                "statusBorder": "rgba(255, 255, 255, 0.06)",
                "statusText": "rgba(242, 245, 248, 0.96)",
                "statusShimmer": "rgba(160, 200, 255, 0.6)",
                "statusCheck": "rgba(130, 200, 130, 0.9)",
                "cursorBg": "rgba(5, 6, 8, 0.92)",
                "cursorBorder": "rgba(255, 255, 255, 0.06)",
                "cursorText": "rgba(242, 245, 248, 0.96)",
                "cursorShimmer": "rgba(160, 200, 255, 0.6)",
            }
        return {
            "mode": "dark-on-light",
            "accent": "rgba(55, 120, 220, 0.85)",
            "boxStroke": "rgba(45, 123, 255, 0.95)",
            "text": "rgba(15, 20, 30, 0.94)",
            "label": "rgba(15, 20, 30, 0.55)",
            "thinking": "rgba(35, 40, 55, 0.75)",
            "panelBg": "rgba(248, 250, 252, 0.94)",
            "panelBorder": "rgba(15, 20, 30, 0.14)",
            "meta": "rgba(15, 20, 30, 0.6)",
            "divider": "rgba(15, 20, 30, 0.5)",
            "shimmer": "rgba(60, 120, 220, 0.85)",
            "statusBg": "rgba(245, 248, 252, 0.96)",
            "statusBorder": "rgba(15, 20, 30, 0.1)",
            "statusText": "rgba(15, 20, 30, 0.94)",
            "statusShimmer": "rgba(60, 120, 220, 0.55)",
            "statusCheck": "rgba(60, 120, 220, 0.9)",
            "cursorBg": "rgba(246, 249, 252, 0.94)",
            "cursorBorder": "rgba(15, 20, 30, 0.1)",
            "cursorText": "rgba(15, 20, 30, 0.94)",
            "cursorShimmer": "rgba(60, 120, 220, 0.55)",
        }

    def _is_dark_at(self, x: int, y: int, threshold: int = None) -> bool:
        screenshot = self._get_screenshot_rgb()
        if screenshot is None:
            return self._last_dark_sample
        width, height = screenshot.size
        if width <= 0 or height <= 0:
            return self._last_dark_sample
        px = min(max(int(x), 0), width - 1)
        py = min(max(int(y), 0), height - 1)

        # Average a local neighborhood for stability.
        radius = 12
        step = 4
        luminance_sum = 0.0
        sample_count = 0

        for dy in range(-radius, radius + 1, step):
            sy = min(max(py + dy, 0), height - 1)
            for dx in range(-radius, radius + 1, step):
                sx = min(max(px + dx, 0), width - 1)
                try:
                    r, g, b = screenshot.getpixel((sx, sy))
                except Exception:
                    continue

                luminance_sum += (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
                sample_count += 1

        # Conservative fallback if sampling failed.
        if sample_count == 0:
            return self._last_dark_sample

        avg_luminance = luminance_sum / sample_count
        active_threshold = threshold if threshold is not None else self.DARK_LUMINANCE_THRESHOLD
        is_dark = avg_luminance < active_threshold
        self._last_dark_sample = is_dark
        return is_dark

    def _theme_for_point(self, x: int, y: int) -> dict:
        prefer_light_text = self._is_dark_at(x, y)
        return self._get_palette(prefer_light_text)

    def _theme_for_text(self, x: int, y: int) -> dict:
        prefer_light_text = self._is_dark_at(x, y, self.INVERTED_PANEL_DARK_THRESHOLD)
        return self._get_palette(not prefer_light_text)

    def _theme_for_status(self) -> dict:
        width, height = get_screen_size()
        if not width or not height:
            screenshot = self._get_screenshot_rgb()
            if screenshot:
                width, height = screenshot.size
        x = int((width or 1920) / 2)
        y = 50
        # Invert for status bubble as well, but use a more lenient threshold
        # for the brighter top strip many desktops/windows have.
        prefer_light_text = self._is_dark_at(x, y, self.STATUS_INVERTED_PANEL_DARK_THRESHOLD)
        return self._get_palette(not prefer_light_text)

    def _theme_for_cursor(self) -> dict:
        x, y = self._last_cursor_pos
        prefer_light_text = self._is_dark_at(x, y, self.INVERTED_PANEL_DARK_THRESHOLD)
        return self._get_palette(not prefer_light_text)

    async def start(self):
        # Disable ping_interval since VisualizationClient (internal) only sends
        # and doesn't run a receive loop to respond to pings
        self._server = await websockets.serve(
            self._handle_client, self.host, self.port, ping_interval=None
        )

    async def stop(self):
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()

    async def wait_forever(self):
        await asyncio.Future()

    async def wait_for_client(self):
        while not self.clients:
            await asyncio.sleep(0.05)

    async def _handle_client(self, websocket):
        self.clients.add(websocket)
        try:
            for box in self.boxes.values():
                await websocket.send(json.dumps(box))
            for text in self.texts.values():
                await websocket.send(json.dumps(text))
            for dot in self.dots.values():
                await websocket.send(json.dumps(dot))

            async for message in websocket:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    continue

                command = payload.get("command")
                if command == "draw_box":
                    if payload.get("autoContrast"):
                        center_x = payload.get("x", 0) + (payload.get("width", 0) / 2)
                        center_y = payload.get("y", 0) + (payload.get("height", 0) / 2)
                        theme = self._theme_for_point(center_x, center_y)
                        payload["stroke"] = theme.get("boxStroke") or theme.get("accent") or payload.get("stroke")
                    self.boxes[payload["id"]] = payload
                    await self._broadcast(payload)
                elif command == "draw_dot":
                    self.dots[payload["id"]] = payload
                    await self._broadcast(payload)
                elif command == "draw_text":
                    theme = self._theme_for_text(payload.get("x", 0), payload.get("y", 0))
                    payload["theme"] = theme
                    payload["color"] = theme.get("accent")
                    self.texts[payload["id"]] = payload
                    await self._broadcast(payload)
                elif command == "remove_box":
                    self.boxes.pop(payload.get("id"), None)
                    await self._broadcast(payload)
                elif command == "remove_dot":
                    self.dots.pop(payload.get("id"), None)
                    await self._broadcast(payload)
                elif command == "remove_text":
                    self.texts.pop(payload.get("id"), None)
                    await self._broadcast(payload)
                elif command == "overlay_hide":
                    await self._broadcast(payload)
                elif command == "show_command_overlay":
                    await self._broadcast(payload)
                elif command == "set_model_name":
                    await self._broadcast(payload)
                elif command == "show_status_bubble":
                    if "theme" in payload and payload.get("theme"):
                        self._active_status_theme = payload["theme"]
                    else:
                        self._active_status_theme = self._theme_for_status()
                        payload["theme"] = self._active_status_theme
                    await self._broadcast(payload)
                elif command == "update_status_bubble":
                    if "theme" in payload and payload.get("theme"):
                        self._active_status_theme = payload["theme"]
                    elif self._active_status_theme is not None:
                        payload["theme"] = self._active_status_theme
                    else:
                        self._active_status_theme = self._theme_for_status()
                        payload["theme"] = self._active_status_theme
                    await self._broadcast(payload)
                elif command == "complete_status_bubble":
                    if "theme" in payload and payload.get("theme"):
                        self._active_status_theme = payload["theme"]
                    elif self._active_status_theme is not None:
                        payload["theme"] = self._active_status_theme
                    else:
                        self._active_status_theme = self._theme_for_status()
                        payload["theme"] = self._active_status_theme
                    await self._broadcast(payload)
                elif command == "hide_status_bubble":
                    self._active_status_theme = None
                    await self._broadcast(payload)
                elif command == "show_cursor_status":
                    if "theme" not in payload:
                        payload["theme"] = self._theme_for_cursor()
                    await self._broadcast(payload)
                elif command == "update_cursor_status":
                    if "theme" not in payload:
                        payload["theme"] = self._theme_for_cursor()
                    await self._broadcast(payload)
                elif command == "hide_cursor_status":
                    await self._broadcast(payload)
                elif command == "set_cursor_status_position":
                    self._last_cursor_pos = (payload.get("x", 0), payload.get("y", 0))
                    await self._broadcast(payload)
                elif command == "clear":
                    self.boxes.clear()
                    self.texts.clear()
                    self.dots.clear()
                    self._active_status_theme = None
                    await self._broadcast(payload)
                elif command == "set_background":
                    await self._broadcast(payload)
                else:
                    event = payload.get("event")
                    if event == "viewport":
                        width = payload.get("width")
                        height = payload.get("height")
                        print(f"viewport: {width}x{height}")
                        if width and height:
                            set_screen_size(int(width), int(height))
                        continue
                    if event == "click":
                        print(f"clicked: {payload.get('id')}")
                    if event == "capture_screenshot":
                        if self.on_capture_screenshot:
                            result = self.on_capture_screenshot()
                            if asyncio.iscoroutine(result):
                                result = await result
                            self._store_screenshot(result)
                        continue
                    if event == "stop_all":
                        if self.on_stop_all:
                            result = self.on_stop_all()
                            if asyncio.iscoroutine(result):
                                await result
                        continue
                    if event == "overlay_input":
                        text = payload.get("text", "")
                        request_id = payload.get("requestId") or payload.get("request_id")
                        now = time.monotonic()

                        # Drop duplicate submit events that can occur during rapid
                        # key/click interactions or transient websocket reconnects.
                        if request_id:
                            expired = [
                                rid for rid, ts in self._seen_overlay_request_ids.items()
                                if (now - ts) > 10.0
                            ]
                            for rid in expired:
                                self._seen_overlay_request_ids.pop(rid, None)
                            if request_id in self._seen_overlay_request_ids:
                                continue
                            self._seen_overlay_request_ids[request_id] = now
                        else:
                            normalized = " ".join(str(text).split())
                            if (
                                normalized
                                and normalized == self._last_overlay_text
                                and (now - self._last_overlay_ts) < 1.2
                            ):
                                continue
                            self._last_overlay_text = normalized
                            self._last_overlay_ts = now

                        if self.on_overlay_input:
                            result = self.on_overlay_input(text)
                            if asyncio.iscoroutine(result):
                                await result
        except ConnectionClosed:
            # Normal path when renderer reloads or disconnects abruptly.
            pass
        finally:
            self.clients.discard(websocket)

    async def _broadcast(self, payload):
        if not self.clients:
            return
        message = json.dumps(payload)
        stale = []
        for client in list(self.clients):
            try:
                await client.send(message)
            except ConnectionClosed:
                stale.append(client)

        for client in stale:
            self.clients.discard(client)
