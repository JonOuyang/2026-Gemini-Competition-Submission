"""
Agentic vision utilities for precision click localization.

This module implements a crop-and-search flow:
1) Crop a coarse region from the current screenshot
2) Run a second vision localization pass inside that crop
3) Map localized coordinates back to full-screen space and click
"""

import os
import re

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


DEFAULT_LOCATOR_MODEL = "gemini-3-flash-preview"
MIN_CROP_SIZE_PX = 32
DEFAULT_CROP_PAD_PX = 400


def _normalize_click_type(type_of_click: str) -> str:
    normalized = str(type_of_click or "").strip().lower()
    if normalized in {"left", "left click", "click"}:
        return "left click"
    if normalized in {"double", "double click", "double left click"}:
        return "double left click"
    if normalized in {"right", "right click"}:
        return "right click"
    raise ValueError(f"Unsupported click type: {type_of_click}")


def _click_at(type_of_click: str, x: float, y: float):
    move_cursor(x, y, duration=0.2)
    if type_of_click == "left click":
        click_left_click()
        return
    if type_of_click == "double left click":
        click_double_left_click()
        return
    if type_of_click == "right click":
        click_right_click()
        return
    raise ValueError(f"Unsupported click type: {type_of_click}")


def _to_pixels(value: float, size: int) -> float:
    """
    Convert supported coordinate formats to pixels for a given axis size.

    Supports:
    - ratio [0, 1]
    - normalized [0, 1000]
    - absolute pixels (>1000 typically)
    """
    val = float(value)
    if 0.0 <= val <= 1.0:
        return val * size
    if 0.0 <= val <= 1000.0:
        return (val / 1000.0) * size
    return val


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _minimal_thinking_config():
    """Return a minimal-thinking config across supported SDK variants."""
    try:
        return types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL,
        )
    except Exception:
        return types.ThinkingConfig(thinking_budget=0)


def _apply_padding(
    left: float,
    top: float,
    right: float,
    bottom: float,
    width: int,
    height: int,
    pad_pixels: float,
    rebalance_edges: bool,
) -> tuple[float, float, float, float]:
    """
    Expand crop bounds by fixed padding.

    If one side hits an edge and rebalance is enabled, shift the clipped padding
    to the opposite side so the target stays closer to center.
    """
    pad = max(float(pad_pixels), 0.0)

    raw_left = left - pad
    raw_right = right + pad
    raw_top = top - pad
    raw_bottom = bottom + pad

    padded_left = _clamp(raw_left, 0, max(width - 1, 0))
    padded_right = _clamp(raw_right, 1, max(width, 1))
    padded_top = _clamp(raw_top, 0, max(height - 1, 0))
    padded_bottom = _clamp(raw_bottom, 1, max(height, 1))

    if rebalance_edges:
        left_clip = max(0.0, padded_left - raw_left)
        right_clip = max(0.0, raw_right - padded_right)
        top_clip = max(0.0, padded_top - raw_top)
        bottom_clip = max(0.0, raw_bottom - padded_bottom)

        if left_clip > 0:
            room = max(0.0, width - padded_right)
            padded_right += min(left_clip, room)
        if right_clip > 0:
            room = max(0.0, padded_left)
            padded_left -= min(right_clip, room)
        if top_clip > 0:
            room = max(0.0, height - padded_bottom)
            padded_bottom += min(top_clip, room)
        if bottom_clip > 0:
            room = max(0.0, padded_top)
            padded_top -= min(bottom_clip, room)

        padded_left = _clamp(padded_left, 0, max(width - 1, 0))
        padded_right = _clamp(padded_right, 1, max(width, 1))
        padded_top = _clamp(padded_top, 0, max(height - 1, 0))
        padded_bottom = _clamp(padded_bottom, 1, max(height, 1))

    return padded_left, padded_top, padded_right, padded_bottom


def _normalize_crop_box(
    crop_bounds: tuple[float, float, float, float],
    width: int,
    height: int,
    pad_pixels: float = DEFAULT_CROP_PAD_PX,
    rebalance_edges: bool = True,
) -> tuple[int, int, int, int]:
    ymin, xmin, ymax, xmax = crop_bounds

    top = _to_pixels(ymin, height)
    left = _to_pixels(xmin, width)
    bottom = _to_pixels(ymax, height)
    right = _to_pixels(xmax, width)

    left, right = sorted((left, right))
    top, bottom = sorted((top, bottom))

    left = _clamp(left, 0, max(width - 1, 0))
    right = _clamp(right, 1, max(width, 1))
    top = _clamp(top, 0, max(height - 1, 0))
    bottom = _clamp(bottom, 1, max(height, 1))

    left, top, right, bottom = _apply_padding(
        left,
        top,
        right,
        bottom,
        width,
        height,
        pad_pixels=pad_pixels,
        rebalance_edges=rebalance_edges,
    )

    if (right - left) < MIN_CROP_SIZE_PX:
        center_x = (left + right) / 2.0
        half = MIN_CROP_SIZE_PX / 2.0
        left = _clamp(center_x - half, 0, max(width - MIN_CROP_SIZE_PX, 0))
        right = _clamp(left + MIN_CROP_SIZE_PX, 1, max(width, 1))

    if (bottom - top) < MIN_CROP_SIZE_PX:
        center_y = (top + bottom) / 2.0
        half = MIN_CROP_SIZE_PX / 2.0
        top = _clamp(center_y - half, 0, max(height - MIN_CROP_SIZE_PX, 0))
        bottom = _clamp(top + MIN_CROP_SIZE_PX, 1, max(height, 1))

    return (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )


def _parse_bbox(text: str) -> tuple[float, float, float, float]:
    numbers = re.findall(r"-?\d+(?:\.\d+)?", str(text or ""))
    if len(numbers) < 4:
        raise ValueError(f"Could not parse bounding box from model response: {text!r}")

    ymin, xmin, ymax, xmax = (float(numbers[0]), float(numbers[1]), float(numbers[2]), float(numbers[3]))
    return ymin, xmin, ymax, xmax


def _check_stop(should_stop):
    if callable(should_stop) and should_stop():
        raise InterruptedError("Stop requested")


def crop_and_search_click(
    screenshot,
    crop_bounds: tuple[float, float, float, float],
    target_description: str,
    type_of_click: str | None = None,
    window_offset: tuple[float, float] = (0.0, 0.0),
    window_scale: tuple[float, float] = (1.0, 1.0),
    model_name: str = DEFAULT_LOCATOR_MODEL,
    should_stop=None,
    perform_click: bool = False,
    pad_pixels: float = DEFAULT_CROP_PAD_PX,
    rebalance_edges: bool = True,
) -> dict:
    """
    Precision click using a crop + second-pass localization.

    Args:
        screenshot: Active-window screenshot used for first-pass reasoning.
        crop_bounds: (ymin, xmin, ymax, xmax) coarse region for zoom-in.
        target_description: What to localize within the crop.
        type_of_click: left click | double left click | right click
        window_offset: Active-window top-left screen offset (x, y).
        window_scale: Image pixel to logical coordinate scale (x, y).
        model_name: Gemini model used for secondary localization.
        should_stop: Optional callback returning True when cancellation is requested.
        perform_click: Whether to click after localization (default False).
        pad_pixels: Fixed padding applied to each side of crop bounds.
        rebalance_edges: Shift clipped padding to opposite side near edges.
    """
    _check_stop(should_stop)

    width, height = screenshot.size
    left, top, right, bottom = _normalize_crop_box(
        crop_bounds,
        width,
        height,
        pad_pixels=pad_pixels,
        rebalance_edges=rebalance_edges,
    )
    cropped = screenshot.crop((left, top, right, bottom))

    crop_w, crop_h = cropped.size
    if crop_w <= 1 or crop_h <= 1:
        raise ValueError("Invalid crop region after normalization")

    prompt = f"""
You are localizing a single clickable UI target inside a cropped screenshot.
Target: {target_description}

Return ONLY one bounding box in this exact format:
[ymin, xmin, ymax, xmax]

Rules:
- Coordinates must be normalized to 0-1000 relative to THIS CROPPED image.
- Box should tightly contain one clickable element.
- Output only the bracketed array, no extra text.
"""

    _check_stop(should_stop)
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=model_name or DEFAULT_LOCATOR_MODEL,
        contents=[cropped, prompt],
        config=types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=64,
            max_output_tokens=64,
            thinking_config=_minimal_thinking_config(),
        ),
    )

    _check_stop(should_stop)
    local_ymin, local_xmin, local_ymax, local_xmax = _parse_bbox(response.text)

    local_top = _to_pixels(local_ymin, crop_h)
    local_left = _to_pixels(local_xmin, crop_w)
    local_bottom = _to_pixels(local_ymax, crop_h)
    local_right = _to_pixels(local_xmax, crop_w)

    local_left, local_right = sorted((local_left, local_right))
    local_top, local_bottom = sorted((local_top, local_bottom))

    local_left = _clamp(local_left, 0, max(crop_w - 1, 0))
    local_right = _clamp(local_right, 1, max(crop_w, 1))
    local_top = _clamp(local_top, 0, max(crop_h - 1, 0))
    local_bottom = _clamp(local_bottom, 1, max(crop_h, 1))

    center_x_in_crop = local_left + ((local_right - local_left) / 2.0)
    center_y_in_crop = local_top + ((local_bottom - local_top) / 2.0)

    x_in_window = left + center_x_in_crop
    y_in_window = top + center_y_in_crop

    scale_x = float(window_scale[0] if window_scale else 1.0)
    scale_y = float(window_scale[1] if window_scale else 1.0)
    if scale_x <= 0:
        scale_x = 1.0
    if scale_y <= 0:
        scale_y = 1.0
    x_in_window_logical = x_in_window / scale_x
    y_in_window_logical = y_in_window / scale_y

    offset_x = float(window_offset[0] if window_offset else 0.0)
    offset_y = float(window_offset[1] if window_offset else 0.0)
    final_x = x_in_window_logical + offset_x
    final_y = y_in_window_logical + offset_y

    resolved_click_type = None
    if perform_click:
        resolved_click_type = _normalize_click_type(type_of_click or "left click")
        _check_stop(should_stop)
        _click_at(resolved_click_type, final_x, final_y)

    return {
        "x": final_x,
        "y": final_y,
        "crop_box": [left, top, right, bottom],
        "click_type": resolved_click_type,
        "target_description": target_description,
    }
