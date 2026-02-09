"""
CLOVIS Agent Tools - Screen annotation capabilities.

This module contains all the tool definitions and wrapper functions for
drawing on the user's screen (bounding boxes, text, pointers, etc.).
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from google.genai import types

from core.settings import get_screen_size, get_viewport_size
from ui.visualization_api.clear_screen import _clear_screen
from ui.visualization_api.create_text import _create_text
from ui.visualization_api.client import get_client
from ui.visualization_api.destroy_box import _destroy_box
from ui.visualization_api.destroy_text import _destroy_text
from ui.visualization_api.draw_bounding_box import _draw_bounding_box
from ui.visualization_api.draw_dot import _draw_dot


# ================================================================================
# ACTION QUEUE - Handles timed execution of visual elements
# ================================================================================

ACTION_QUEUE = deque()
_ACTION_TASK = None
_SCREEN_SIZE = None
_VIEWPORT_SIZE = None
_LAST_DIRECT_RESPONSE = None
_WAITED_AFTER_DIRECT_RESPONSE = True
_ACTIVE_TEXT_RECTS = {}

# Approximate runtime layout model for `.ai-ar-panel` in `overlay_text.css`.
_TEXT_PANEL_MAX_WIDTH_PX = 320
_TEXT_PANEL_MIN_WIDTH_PX = 96
_TEXT_PANEL_MIN_HEIGHT_PX = 44
_TEXT_HORIZONTAL_PADDING_PX = 40  # 20px left + 20px right
_TEXT_VERTICAL_PADDING_PX = 32  # 16px top + 16px bottom
_TEXT_LINE_HEIGHT_MULTIPLIER = 1.6
_TEXT_CHAR_WIDTH_MULTIPLIER = 0.56
_TEXT_SIZE_SAFETY_WIDTH_PX = 8
_TEXT_SIZE_SAFETY_HEIGHT_PX = 16
_TEXT_VIEWPORT_MARGIN_PX = 8
_TEXT_LAYOUT_STEP_PX = 28
_TEXT_LAYOUT_MAX_RINGS = 10
_TEXT_OVERLAP_BUFFER_PX = 0


def _get_sizes():
    global _SCREEN_SIZE, _VIEWPORT_SIZE
    if not _SCREEN_SIZE or not _VIEWPORT_SIZE:
        _SCREEN_SIZE = get_screen_size()
        _VIEWPORT_SIZE = get_viewport_size()
    return _SCREEN_SIZE, _VIEWPORT_SIZE


def denormalize(norm_x, norm_y):
    """Convert normalized coordinates (0-1000) to pixel values."""
    screen_size, viewport_size = _get_sizes()
    viewport_width, viewport_height = viewport_size
    screen_width, screen_height = screen_size

    width = viewport_width or screen_width
    height = viewport_height or screen_height

    if not width or not height:
        raise RuntimeError("Missing viewport/screen size; cannot denormalize coordinates.")
    denorm_x, denorm_y = norm_x, norm_y

    if 0 <= norm_x <= 1000:
        denorm_x = int(norm_x / 1000 * width)
    if 0 <= norm_y <= 1000:
        denorm_y = int(norm_y / 1000 * height)
    return denorm_x, denorm_y


def _get_command_anchor():
    """Get the anchor position for direct response text."""
    screen_size, viewport_size = _get_sizes()
    viewport_width, viewport_height = viewport_size
    screen_width, screen_height = screen_size

    width = viewport_width or screen_width
    height = viewport_height or screen_height
    if not width or not height:
        raise RuntimeError("Missing viewport/screen size; cannot place direct response.")

    center_x = int(width * 0.5)
    base_y = int(height * 0.5) - 20
    response_y = base_y + 60
    return center_x, response_y


async def _hide_command_overlay():
    client = await get_client()
    await client.send({"command": "overlay_hide", "id": "direct_response"})


async def set_model_name(name: str):
    """Set the model name displayed in the response bubble."""
    client = await get_client()
    await client.send({"command": "set_model_name", "name": name})


# ================================================================================
# ACTION QUEUE HANDLERS
# ================================================================================

def queue_action(time: float, func, args, kwargs=None):
    ACTION_QUEUE.append((time, func, args, kwargs or {}))
    _ensure_queue_processor()


def _ensure_queue_processor():
    """Start the queue processor task if not already running."""
    global _ACTION_TASK

    if _ACTION_TASK is not None and not _ACTION_TASK.done():
        return

    try:
        loop = asyncio.get_running_loop()
        _ACTION_TASK = loop.create_task(_run_queue_async())
    except RuntimeError:
        pass


async def _run_queue_async():
    """Process queued actions with their time delays."""
    global _LAST_DIRECT_RESPONSE, _WAITED_AFTER_DIRECT_RESPONSE
    last_time = 0.0

    while True:
        if not ACTION_QUEUE:
            last_time = 0.0
            await asyncio.sleep(0.05)
            continue

        time_s, func, args, kwargs = ACTION_QUEUE.popleft()

        # Handle direct_response delay
        if _LAST_DIRECT_RESPONSE and not _WAITED_AFTER_DIRECT_RESPONSE:
            elapsed = time.monotonic() - _LAST_DIRECT_RESPONSE
            if elapsed < 4.0:
                await asyncio.sleep(4.0 - elapsed)
            await _hide_command_overlay()
            _WAITED_AFTER_DIRECT_RESPONSE = True

        delay = max(0.0, float(time_s) - last_time)
        if delay:
            await asyncio.sleep(delay)
        await func(*args, **kwargs)
        last_time = float(time_s)


def _dispatch_now(coro):
    """Schedule a coroutine to run immediately on the current event loop."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        pass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _viewport_dimensions() -> tuple[int, int]:
    """Return overlay viewport dimensions in pixels."""
    screen_size, viewport_size = _get_sizes()
    viewport_width, viewport_height = viewport_size
    screen_width, screen_height = screen_size
    width = int(viewport_width or screen_width or 1)
    height = int(viewport_height or screen_height or 1)
    return max(width, 1), max(height, 1)


def _normalize_align(align: str | None) -> str:
    value = str(align or "left").strip().lower()
    if value not in {"left", "center", "right"}:
        return "left"
    return value


def _normalize_baseline(baseline: str | None) -> str:
    value = str(baseline or "top").strip().lower()
    if value in {"middle", "center"}:
        return "middle"
    if value == "bottom":
        return "bottom"
    return "top"


def _wrap_line_to_width(raw_line: str, max_chars: int) -> list[str]:
    if max_chars <= 1:
        return list(raw_line) if raw_line else [""]

    words = raw_line.split(" ")
    lines = []
    current = ""

    def _append_long_word(word: str, existing: str):
        current_local = existing
        for idx in range(0, len(word), max_chars):
            chunk = word[idx:idx + max_chars]
            if idx == 0:
                current_local = chunk
            else:
                lines.append(current_local)
                current_local = chunk
        return current_local

    for word in words:
        if not current:
            if len(word) <= max_chars:
                current = word
            else:
                current = _append_long_word(word, current)
            continue

        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue

        lines.append(current)
        if len(word) <= max_chars:
            current = word
        else:
            current = _append_long_word(word, "")

    lines.append(current if current else "")
    return lines


def _estimate_text_panel_size(text: str, font_size: int) -> tuple[int, int]:
    """
    Estimate rendered text-bubble dimensions using CSS-driven approximations.

    This considers wrapped lines, max panel width, and bubble padding so collision
    checks use the entire panel footprint instead of only the anchor point.
    """
    safe_text = str(text or "")
    safe_font_size = max(int(font_size or 18), 10)

    content_max_width = max(_TEXT_PANEL_MAX_WIDTH_PX - _TEXT_HORIZONTAL_PADDING_PX, 40)
    char_width = max(safe_font_size * _TEXT_CHAR_WIDTH_MULTIPLIER, 4.5)
    max_chars_per_line = max(1, int(content_max_width // char_width))

    wrapped_lines = []
    for raw_line in (safe_text.splitlines() or [""]):
        wrapped_lines.extend(_wrap_line_to_width(raw_line, max_chars_per_line))
    wrapped_lines = wrapped_lines or [""]

    line_count = max(len(wrapped_lines), 1)
    longest_line_chars = max((len(line) for line in wrapped_lines), default=1)

    content_width = min(
        content_max_width,
        max(char_width * max(longest_line_chars, 2), 24),
    )
    line_height = max(safe_font_size * _TEXT_LINE_HEIGHT_MULTIPLIER, safe_font_size + 4)
    content_height = max(line_count * line_height, line_height)

    panel_width = int(round(_clamp(
        content_width + _TEXT_HORIZONTAL_PADDING_PX + _TEXT_SIZE_SAFETY_WIDTH_PX,
        _TEXT_PANEL_MIN_WIDTH_PX,
        _TEXT_PANEL_MAX_WIDTH_PX,
    )))
    panel_height = int(round(max(
        content_height + _TEXT_VERTICAL_PADDING_PX + _TEXT_SIZE_SAFETY_HEIGHT_PX,
        _TEXT_PANEL_MIN_HEIGHT_PX,
    )))
    return panel_width, panel_height


def _anchor_to_rect(
    anchor_x: float,
    anchor_y: float,
    panel_width: int,
    panel_height: int,
    align: str,
    baseline: str,
    viewport_width: int,
    viewport_height: int,
) -> tuple[int, int, tuple[float, float, float, float]]:
    if align == "center":
        left = anchor_x - (panel_width / 2.0)
    elif align == "right":
        left = anchor_x - panel_width
    else:
        left = anchor_x

    if baseline == "middle":
        top = anchor_y - (panel_height / 2.0)
    elif baseline == "bottom":
        top = anchor_y - panel_height
    else:
        top = anchor_y

    horizontal_margin = _TEXT_VIEWPORT_MARGIN_PX
    vertical_margin = _TEXT_VIEWPORT_MARGIN_PX
    if panel_width + (2 * horizontal_margin) > viewport_width:
        horizontal_margin = 0
    if panel_height + (2 * vertical_margin) > viewport_height:
        vertical_margin = 0

    min_left = horizontal_margin
    min_top = vertical_margin
    max_left = max(viewport_width - panel_width - horizontal_margin, min_left)
    max_top = max(viewport_height - panel_height - vertical_margin, min_top)
    clamped_left = _clamp(left, min_left, max_left)
    clamped_top = _clamp(top, min_top, max_top)

    if align == "center":
        resolved_x = clamped_left + (panel_width / 2.0)
    elif align == "right":
        resolved_x = clamped_left + panel_width
    else:
        resolved_x = clamped_left

    if baseline == "middle":
        resolved_y = clamped_top + (panel_height / 2.0)
    elif baseline == "bottom":
        resolved_y = clamped_top + panel_height
    else:
        resolved_y = clamped_top

    rect = (
        float(clamped_left),
        float(clamped_top),
        float(clamped_left + panel_width),
        float(clamped_top + panel_height),
    )
    return int(round(resolved_x)), int(round(resolved_y)), rect


def _rects_overlap(
    rect_a: tuple[float, float, float, float],
    rect_b: tuple[float, float, float, float],
    buffer: int = 0,
) -> bool:
    a_left, a_top, a_right, a_bottom = rect_a
    b_left, b_top, b_right, b_bottom = rect_b
    return (
        a_left < (b_right - buffer)
        and a_right > (b_left + buffer)
        and a_top < (b_bottom - buffer)
        and a_bottom > (b_top + buffer)
    )


def _intersection_area(
    rect_a: tuple[float, float, float, float],
    rect_b: tuple[float, float, float, float],
) -> float:
    a_left, a_top, a_right, a_bottom = rect_a
    b_left, b_top, b_right, b_bottom = rect_b
    width = max(0.0, min(a_right, b_right) - max(a_left, b_left))
    height = max(0.0, min(a_bottom, b_bottom) - max(a_top, b_top))
    return width * height


def _has_text_overlap(
    rect: tuple[float, float, float, float],
    ignore_text_id: str | None = None,
) -> bool:
    for other_id, other_rect in _ACTIVE_TEXT_RECTS.items():
        if ignore_text_id and other_id == ignore_text_id:
            continue
        if _rects_overlap(rect, other_rect, _TEXT_OVERLAP_BUFFER_PX):
            return True
    return False


def _overlap_score(
    rect: tuple[float, float, float, float],
    ignore_text_id: str | None = None,
) -> float:
    score = 0.0
    for other_id, other_rect in _ACTIVE_TEXT_RECTS.items():
        if ignore_text_id and other_id == ignore_text_id:
            continue
        score += _intersection_area(rect, other_rect)
    return score


def _resolve_non_overlapping_anchor(
    anchor_x: int,
    anchor_y: int,
    text: str,
    font_size: int,
    align: str | None,
    baseline: str | None,
    text_id: str | None,
) -> tuple[int, int, tuple[float, float, float, float]]:
    viewport_width, viewport_height = _viewport_dimensions()
    norm_align = _normalize_align(align)
    norm_baseline = _normalize_baseline(baseline)
    panel_width, panel_height = _estimate_text_panel_size(text, font_size)

    resolved_x, resolved_y, base_rect = _anchor_to_rect(
        anchor_x,
        anchor_y,
        panel_width,
        panel_height,
        norm_align,
        norm_baseline,
        viewport_width,
        viewport_height,
    )
    if not _has_text_overlap(base_rect, ignore_text_id=text_id):
        return resolved_x, resolved_y, base_rect

    best = (resolved_x, resolved_y, base_rect)
    best_score = _overlap_score(base_rect, ignore_text_id=text_id)
    best_distance = 0

    for ring in range(1, _TEXT_LAYOUT_MAX_RINGS + 1):
        delta = ring * _TEXT_LAYOUT_STEP_PX
        offsets = (
            (0, -delta),
            (0, delta),
            (delta, 0),
            (-delta, 0),
            (delta, -delta),
            (-delta, -delta),
            (delta, delta),
            (-delta, delta),
            (2 * delta, 0),
            (-2 * delta, 0),
            (0, 2 * delta),
            (0, -2 * delta),
        )
        for dx, dy in offsets:
            cand_x, cand_y, cand_rect = _anchor_to_rect(
                anchor_x + dx,
                anchor_y + dy,
                panel_width,
                panel_height,
                norm_align,
                norm_baseline,
                viewport_width,
                viewport_height,
            )
            if not _has_text_overlap(cand_rect, ignore_text_id=text_id):
                return cand_x, cand_y, cand_rect

            score = _overlap_score(cand_rect, ignore_text_id=text_id)
            distance = abs(dx) + abs(dy)
            if score < best_score or (score == best_score and distance < best_distance):
                best = (cand_x, cand_y, cand_rect)
                best_score = score
                best_distance = distance

    return best


async def _create_text_non_overlapping(
    x: int,
    y: int,
    text: str,
    text_id: str | None,
    font_size: int,
    font_family: str,
    align: str | None,
    baseline: str | None,
    source: str = "clovis",
):
    resolved_text_id = text_id or f"text_{uuid.uuid4().hex[:8]}"
    resolved_x, resolved_y, rect = _resolve_non_overlapping_anchor(
        int(x),
        int(y),
        text,
        int(font_size or 18),
        align,
        baseline,
        resolved_text_id,
    )
    if resolved_x != int(x) or resolved_y != int(y):
        print(
            "[CLOVIS][layout] nudged text "
            f"{resolved_text_id} from ({int(x)},{int(y)}) to ({resolved_x},{resolved_y})"
        )

    created_id = await _create_text(
        resolved_x,
        resolved_y,
        text,
        resolved_text_id,
        font_size,
        font_family,
        align,
        baseline,
        source,
    )
    _ACTIVE_TEXT_RECTS[created_id] = rect
    return created_id


async def _clear_screen_with_layout_reset():
    _ACTIVE_TEXT_RECTS.clear()
    await _clear_screen()


async def _destroy_text_with_layout_reset(text_id: str):
    _ACTIVE_TEXT_RECTS.pop(text_id, None)
    await _destroy_text(text_id)


def stop_all_actions():
    """Immediately stop and clear queued overlay actions."""
    global _ACTION_TASK, _LAST_DIRECT_RESPONSE, _WAITED_AFTER_DIRECT_RESPONSE
    ACTION_QUEUE.clear()
    if _ACTION_TASK is not None and not _ACTION_TASK.done():
        _ACTION_TASK.cancel()
    _ACTION_TASK = None
    _LAST_DIRECT_RESPONSE = None
    _WAITED_AFTER_DIRECT_RESPONSE = True
    _ACTIVE_TEXT_RECTS.clear()


# ================================================================================
# TOOL WRAPPER FUNCTIONS
# ================================================================================

def clear_screen(time: float):
    queue_action(time, _clear_screen_with_layout_reset, (), {})


def create_text(
    time: float,
    x: int,
    y: int,
    text: str,
    font_size: int = 18,
    font_family: str = "Helvetica",
    align: str = "left",
    baseline: str = "top",
    text_id: str = None,
):
    x, y = denormalize(x, y)
    queue_action(
        time,
        _create_text_non_overlapping,
        (x, y, text, text_id, font_size, font_family, align, baseline, "clovis"),
        {}
    )


def direct_response(
    text: str,
    font_size: int = 18,
    font_family: str = "Helvetica",
    source: str = "clovis",
):
    global _LAST_DIRECT_RESPONSE, _WAITED_AFTER_DIRECT_RESPONSE
    _LAST_DIRECT_RESPONSE = time.monotonic()
    _WAITED_AFTER_DIRECT_RESPONSE = False
    x, y = _get_command_anchor()
    _dispatch_now(_create_text(
        x,
        y,
        text,
        "direct_response",
        font_size,
        font_family,
        "left",
        "top",
        source,
    ))


def create_text_for_box(
    time: float,
    box: dict,
    text: str,
    position: str = "top",
    font_size: int = 18,
    font_family: str = "Helvetica",
    align: str = None,
    padding: int = 6,
):
    box_x, box_y = denormalize(box["x"], box["y"])
    box_w, box_h = denormalize(box["width"], box["height"])
    box = {"x": box_x, "y": box_y, "width": box_w, "height": box_h}
    center_x = box["x"] + (box["width"] / 2)
    center_y = box["y"] + (box["height"] / 2)

    if position == "top":
        anchor_x = center_x
        anchor_y = box["y"] - padding
        baseline = "bottom"
        default_align = "center"
    elif position == "bottom":
        anchor_x = center_x
        anchor_y = box["y"] + box["height"] + padding
        baseline = "top"
        default_align = "center"
    elif position == "left":
        anchor_x = box["x"] - padding
        anchor_y = center_y
        baseline = "middle"
        default_align = "right"
    elif position == "right":
        anchor_x = box["x"] + box["width"] + padding
        anchor_y = center_y
        baseline = "middle"
        default_align = "left"
    else:
        raise ValueError("position must be one of: top, bottom, left, right")

    anchor_align = align or default_align
    queue_action(
        time,
        _create_text_non_overlapping,
        (
            int(anchor_x),
            int(anchor_y),
            text,
            None,
            font_size,
            font_family,
            anchor_align,
            baseline,
            "clovis",
        ),
        {},
    )


def destroy_box(time: float, box_id: str):
    queue_action(time, _destroy_box, (box_id,), {})


def destroy_text(time: float, text_id: str):
    queue_action(time, _destroy_text_with_layout_reset, (text_id,), {})


def draw_bounding_box(
    time: float,
    y_min: int,
    x_min: int,
    y_max: int,
    x_max: int,
    box_id: str = None,
    stroke: str | None = "#66B7FF",
    stroke_width: int = 5,
    opacity: float = 0.8,
    auto_contrast: bool = False,
    fill: str | None = None,
):
    x_min, y_min = denormalize(x_min, y_min)
    x_max, y_max = denormalize(x_max, y_max)
    queue_action(
        time,
        _draw_bounding_box,
        (y_min, x_min, y_max, x_max, box_id, stroke, stroke_width, opacity, auto_contrast, fill),
        {},
    )


def draw_pointer_to_object(
    time: float,
    x_pos: int,
    y_pos: int,
    text: str,
    text_x: int,
    text_y: int,
    point_id: str = None,
    dot_color: str = "#ffffff",
    ring_color: str = "#66B7FF",
    ring_radius: int = None,
):
    """
    Draw a pointer dot at (x_pos, y_pos) with a text label at (text_x, text_y).
    A thin white line automatically connects the dot to the center of the text bubble.
    """
    link_id = point_id or f"ptr_{uuid.uuid4().hex[:8]}"
    text_id = f"{link_id}_text"

    x_pos, y_pos = denormalize(x_pos, y_pos)
    text_x, text_y = denormalize(text_x, text_y)

    queue_action(
        time,
        _draw_dot,
        (x_pos, y_pos, link_id, 6, dot_color, ring_color, text_id, ring_radius),
        {},
    )
    queue_action(
        time,
        _create_text_non_overlapping,
        (text_x, text_y, text, text_id, 18, "Helvetica", "left", "top", "clovis"),
        {},
    )


# ================================================================================
# TOOL DECLARATIONS (for Gemini function calling)
# ================================================================================

draw_bounding_box_declaration = {
    "name": "draw_bounding_box",
    "description": "Draw a bounding box using Gemini-style coordinates (y_min, x_min, y_max, x_max).",
    "parameters": {
        "type": "object",
        "properties": {
            "time": {"type": "number", "description": "Time offset in seconds for when to run this action."},
            "y_min": {"type": "integer", "description": "Top edge coordinate in pixels."},
            "x_min": {"type": "integer", "description": "Left edge coordinate in pixels."},
            "y_max": {"type": "integer", "description": "Bottom edge coordinate in pixels."},
            "x_max": {"type": "integer", "description": "Right edge coordinate in pixels."},
            "box_id": {"type": "string", "description": "Optional unique ID for the box."},
            "stroke": {"type": "string", "description": "Stroke color hex code.", "default": "#66B7FF"},
            "stroke_width": {"type": "integer", "description": "Border width in pixels.", "default": 5},
            "opacity": {"type": "number", "description": "Opacity from 0 to 1.", "default": 0.8},
            "auto_contrast": {"type": "boolean", "description": "Choose stroke color based on background contrast.", "default": False},
            "fill": {"type": "string", "description": "Optional fill color (CSS color string)."},
        },
        "required": ["time", "y_min", "x_min", "y_max", "x_max"],
    },
}

draw_point_declaration = {
    "name": "draw_pointer_to_object",
    "description": "Draw a dot at (x_pos, y_pos) pointing to an object, with a text label at (text_x, text_y). A thin white line automatically connects the dot to the text bubble center.",
    "parameters": {
        "type": "object",
        "properties": {
            "time": {"type": "number", "description": "Time offset in seconds for when to run this action."},
            "x_pos": {"type": "integer", "description": "X position of the dot in pixels."},
            "y_pos": {"type": "integer", "description": "Y position of the dot in pixels."},
            "text": {"type": "string", "description": "The label text to display."},
            "text_x": {"type": "integer", "description": "X position of the text label in pixels."},
            "text_y": {"type": "integer", "description": "Y position of the text label in pixels."},
            "point_id": {"type": "string", "description": "Optional unique ID for the pointer."},
            "dot_color": {"type": "string", "description": "Dot fill color.", "default": "#ffffff"},
            "ring_color": {"type": "string", "description": "Ring color.", "default": "#66B7FF"},
            "ring_radius": {"type": "integer", "description": "Optional ring radius in pixels."},
        },
        "required": ["time", "x_pos", "y_pos", "text", "text_x", "text_y"],
    },
}

create_text_declaration = {
    "name": "create_text",
    "description": "Draw a text label at an (x, y) anchor point.",
    "parameters": {
        "type": "object",
        "properties": {
            "time": {"type": "number", "description": "Time offset in seconds for when to run this action."},
            "x": {"type": "integer", "description": "X coordinate in pixels."},
            "y": {"type": "integer", "description": "Y coordinate in pixels."},
            "text": {"type": "string", "description": "Label text to render."},
            "font_size": {"type": "integer", "description": "Font size in pixels.", "default": 18},
            "font_family": {"type": "string", "description": "Font family name.", "default": "Helvetica"},
            "align": {"type": "string", "description": "Canvas textAlign value.", "default": "left"},
            "baseline": {"type": "string", "description": "Canvas textBaseline value.", "default": "top"},
            "text_id": {"type": "string", "description": "Optional unique ID for the text label."},
        },
        "required": ["time", "x", "y", "text"],
    },
}

create_text_for_box_declaration = {
    "name": "create_text_for_box",
    "description": "Draw a text label relative to a bounding box.",
    "parameters": {
        "type": "object",
        "properties": {
            "time": {"type": "number", "description": "Time offset in seconds for when to run this action."},
            "box": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "Box left edge."},
                    "y": {"type": "integer", "description": "Box top edge."},
                    "width": {"type": "integer", "description": "Box width."},
                    "height": {"type": "integer", "description": "Box height."},
                },
                "required": ["x", "y", "width", "height"],
            },
            "text": {"type": "string", "description": "Label text to render."},
            "position": {
                "type": "string",
                "enum": ["top", "bottom", "left", "right"],
                "description": "Placement relative to the box.",
                "default": "top",
            },
            "font_size": {"type": "integer", "description": "Font size in pixels.", "default": 18},
            "font_family": {"type": "string", "description": "Font family name.", "default": "Helvetica"},
            "align": {"type": "string", "description": "Canvas textAlign value."},
            "padding": {"type": "integer", "description": "Pixels between text and box.", "default": 6},
        },
        "required": ["time", "box", "text"],
    },
}

direct_response_declaration = {
    "name": "direct_response",
    "description": "Respond directly to the user, without any fancy UI display. Meant for queries that do not involve screen annotations.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Response text to render."},
            "font_size": {"type": "integer", "description": "Font size in pixels.", "default": 18},
            "font_family": {"type": "string", "description": "Font family name.", "default": "Helvetica"},
        },
        "required": ["text"],
    },
}

clear_screen_declaration = {
    "name": "clear_screen",
    "description": "Clear all visual elements on screen.",
    "parameters": {
        "type": "object",
        "properties": {
            "time": {"type": "number", "description": "Time offset in seconds for when to run this action."},
        },
        "required": ["time"],
    },
}

destroy_box_declaration = {
    "name": "destroy_box",
    "description": "Remove a bounding box by ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "time": {"type": "number", "description": "Time offset in seconds for when to run this action."},
            "box_id": {"type": "string", "description": "ID of the box to remove."},
        },
        "required": ["time", "box_id"],
    },
}

destroy_text_declaration = {
    "name": "destroy_text",
    "description": "Remove a text label by ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "time": {"type": "number", "description": "Time offset in seconds for when to run this action."},
            "text_id": {"type": "string", "description": "ID of the text to remove."},
        },
        "required": ["time", "text_id"],
    },
}


# ================================================================================
# TOOL SETS
# ================================================================================

CLOVIS_TOOLS = [types.Tool(function_declarations=[
    draw_bounding_box_declaration,
    draw_point_declaration,
    create_text_declaration,
    direct_response_declaration,
    create_text_for_box_declaration,
    clear_screen_declaration,
    destroy_box_declaration,
    destroy_text_declaration
])]

CLOVIS_TOOL_MAP = {
    "draw_bounding_box": draw_bounding_box,
    "draw_pointer_to_object": draw_pointer_to_object,
    "create_text": create_text,
    "direct_response": direct_response,
    "create_text_for_box": create_text_for_box,
    "clear_screen": clear_screen,
    "destroy_box": destroy_box,
    "destroy_text": destroy_text,
}
