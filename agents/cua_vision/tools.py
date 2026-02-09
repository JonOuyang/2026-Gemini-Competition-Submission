"""
CUA Vision Agent - Tool Declarations and Functions

Contains all tool declarations for the vision-based computer use agent,
including screen interaction, memory, and input functions.
"""

import inspect
import os
import time

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageGrab
import pygetwindow as gw
import pyautogui

try:
    from google.genai import types
except ImportError:
    print('Google Gemini dependencies have not been installed')

from agents.cua_vision.keyboard import (
    move_cursor,
    type_string,
    press_ctrl_hotkey,
    press_alt_hotkey,
    click_left_click,
    hold_down_left_click,
    hold_down_right_click,
    release_left_click,
    release_right_click,
    click_right_click,
    click_double_left_click,
    press_key_for_duration,
    hold_down_key,
    release_held_key,
)
from core.settings import get_clovis_model
from agents.cua_vision.agentic_vision import crop_and_search_click
from agents.cua_vision.legacy_locator import legacy_find_and_click_element
from integrations.audio import tts_speak

load_dotenv()


# ================================================================================
# GLOBAL STATE
# ================================================================================

memory_text = []
memory_image = []

execution_history = None
master_prompt = None
retries = 0
stop_requested = False
last_capture_context = None
last_capture_image = None

TOOL_METADATA_KEYS = {"status_text", "target_description"}

# Auto-refinement policy for small targets.
AUTO_FORCE_ZOOM_MIN_SIDE_LOGICAL_PX = 96
AUTO_FORCE_ZOOM_MAX_AREA_LOGICAL_PX2 = 14000
FORCED_ZOOM_PAD_PX = 400


# ================================================================================
# STATE HELPERS
# ================================================================================

def reset_state():
    """Reset all global state for a new task."""
    global memory_text, memory_image, execution_history, master_prompt, retries, last_capture_context, last_capture_image
    memory_text = []
    memory_image = []
    execution_history = None
    master_prompt = None
    retries = 0
    last_capture_context = None
    last_capture_image = None


def get_memory():
    """Get current memory state."""
    return memory_text, memory_image


def request_stop():
    """Request that the current CUA vision task stop as soon as possible."""
    global stop_requested
    stop_requested = True


def clear_stop_request():
    """Clear any pending stop request before starting a new task."""
    global stop_requested
    stop_requested = False


def is_stop_requested() -> bool:
    """Return whether a stop request has been issued."""
    return stop_requested


def _set_last_capture_context(
    width: int,
    height: int,
    logical_width: int,
    logical_height: int,
    offset_x: float,
    offset_y: float,
    scale_x: float,
    scale_y: float,
    mode: str,
):
    """Store the most recent capture frame metadata for coordinate remapping."""
    global last_capture_context
    last_capture_context = {
        "width": int(width),
        "height": int(height),
        "logical_width": int(logical_width),
        "logical_height": int(logical_height),
        "offset_x": float(offset_x),
        "offset_y": float(offset_y),
        "scale_x": float(scale_x),
        "scale_y": float(scale_y),
        "mode": mode,
    }


def _get_last_capture_context() -> dict | None:
    """Get the most recent capture frame metadata."""
    return last_capture_context


def _set_last_capture_image(image: Image.Image):
    """Store the last capture image used for model reasoning."""
    global last_capture_image
    try:
        last_capture_image = image.copy()
    except Exception:
        last_capture_image = image


def _get_last_capture_image() -> Image.Image | None:
    """Get a copy of the last capture image if available."""
    if last_capture_image is None:
        return None
    try:
        return last_capture_image.copy()
    except Exception:
        return last_capture_image


# ================================================================================
# MEMORY FUNCTIONS
# ================================================================================

def remember_information(thing_to_remember: str):
    """Remember information for later use."""
    memory_text.append(thing_to_remember)
    try:
        bbox = _get_active_window_bbox()
        if bbox:
            memory_image.append(ImageGrab.grab(bbox=bbox))
        else:
            memory_image.append(ImageGrab.grab())
    except Exception as e:
        print(f"Could not capture memory image: {e}")
    print(f"Remembered: {thing_to_remember}")


def task_is_complete(text: str = "Done."):
    """Signal task completion and provide concise spoken confirmation."""
    message = str(text or "").strip()
    if not message:
        message = "Done."
    tts_speak(message)


# ================================================================================
# SCREEN CAPTURE UTILITIES
# ================================================================================

def capture_active_window() -> Image.Image:
    """Capture the currently active window."""
    try:
        bbox = _get_active_window_bbox()
        if bbox:
            image = ImageGrab.grab(bbox=bbox)
            logical_width = max(int(bbox[2] - bbox[0]), 1)
            logical_height = max(int(bbox[3] - bbox[1]), 1)
            scale_x = float(image.size[0]) / float(logical_width)
            scale_y = float(image.size[1]) / float(logical_height)
            _set_last_capture_context(
                width=image.size[0],
                height=image.size[1],
                logical_width=logical_width,
                logical_height=logical_height,
                offset_x=bbox[0],
                offset_y=bbox[1],
                scale_x=scale_x,
                scale_y=scale_y,
                mode="active_window",
            )
            _set_last_capture_image(image)
            return image
    except Exception as e:
        print(f"Error capturing active window: {e}")

    image = ImageGrab.grab()
    try:
        logical_width, logical_height = pyautogui.size()
    except Exception:
        logical_width, logical_height = image.size
    logical_width = max(int(logical_width), 1)
    logical_height = max(int(logical_height), 1)
    scale_x = float(image.size[0]) / float(logical_width)
    scale_y = float(image.size[1]) / float(logical_height)
    _set_last_capture_context(
        width=image.size[0],
        height=image.size[1],
        logical_width=logical_width,
        logical_height=logical_height,
        offset_x=0.0,
        offset_y=0.0,
        scale_x=scale_x,
        scale_y=scale_y,
        mode="full_screen",
    )
    _set_last_capture_image(image)
    return image


def get_active_window_title() -> str:
    """Get the title of the currently active window."""
    try:
        return gw.getActiveWindowTitle() or "Unknown"
    except Exception:
        return "Unknown"


def _get_active_window_bbox():
    """
    Return active window bounds as (left, top, right, bottom), or None.

    Some pygetwindow backends can return a string title from getActiveWindow();
    this helper normalizes that shape and avoids attribute errors.
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


def _to_pixels(value: float, size: int) -> float:
    """Convert ratio/normalized/pixel coordinate formats to pixels."""
    val = float(value)
    if 0.0 <= val <= 1.0:
        return val * size
    if 0.0 <= val <= 1000.0:
        return (val / 1000.0) * size
    return val


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _bbox_center_to_screen_coords(ymin: float, xmin: float, ymax: float, xmax: float) -> tuple[float, float]:
    """Map a bbox center from the last model frame to absolute screen coordinates."""
    context = _get_last_capture_context()
    if not context:
        capture_active_window()
        context = _get_last_capture_context()
    if not context:
        raise RuntimeError("No capture context available for bbox coordinate mapping")

    width = int(context.get("logical_width") or context["width"])
    height = int(context.get("logical_height") or context["height"])
    offset_x = float(context["offset_x"])
    offset_y = float(context["offset_y"])

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

    center_x_window = left + ((right - left) / 2.0)
    center_y_window = top + ((bottom - top) / 2.0)

    return (center_x_window + offset_x, center_y_window + offset_y)


def _bbox_logical_dimensions(ymin: float, xmin: float, ymax: float, xmax: float) -> tuple[float, float]:
    """Return bbox width/height in logical screen pixels."""
    context = _get_last_capture_context()
    if not context:
        capture_active_window()
        context = _get_last_capture_context()
    if not context:
        raise RuntimeError("No capture context available for bbox sizing")

    width = int(context.get("logical_width") or context["width"])
    height = int(context.get("logical_height") or context["height"])

    top = _to_pixels(ymin, height)
    left = _to_pixels(xmin, width)
    bottom = _to_pixels(ymax, height)
    right = _to_pixels(xmax, width)
    return (abs(right - left), abs(bottom - top))


def _should_force_zoom(width_px: float, height_px: float) -> bool:
    """Decide whether to force precision crop refinement for small targets."""
    w = max(float(width_px), 0.0)
    h = max(float(height_px), 0.0)
    area = w * h
    return (
        (w <= AUTO_FORCE_ZOOM_MIN_SIDE_LOGICAL_PX and h <= AUTO_FORCE_ZOOM_MIN_SIDE_LOGICAL_PX)
        or (area <= AUTO_FORCE_ZOOM_MAX_AREA_LOGICAL_PX2)
    )


def _bbox_to_capture_pixel_box(ymin: float, xmin: float, ymax: float, xmax: float) -> tuple[float, float, float, float]:
    """
    Map bbox args to pixel coordinates on the stored capture image.

    Args are interpreted in logical coordinates (0-1000/0-1/logical px),
    then scaled into capture-image pixels.
    """
    context = _get_last_capture_context()
    if not context:
        capture_active_window()
        context = _get_last_capture_context()
    if not context:
        raise RuntimeError("No capture context available for bbox pixel mapping")

    logical_width = int(context.get("logical_width") or context["width"])
    logical_height = int(context.get("logical_height") or context["height"])
    scale_x = float(context.get("scale_x", 1.0))
    scale_y = float(context.get("scale_y", 1.0))
    if scale_x <= 0:
        scale_x = 1.0
    if scale_y <= 0:
        scale_y = 1.0

    top = _to_pixels(ymin, logical_height)
    left = _to_pixels(xmin, logical_width)
    bottom = _to_pixels(ymax, logical_height)
    right = _to_pixels(xmax, logical_width)

    left, right = sorted((left, right))
    top, bottom = sorted((top, bottom))

    left = _clamp(left, 0, max(logical_width - 1, 0))
    right = _clamp(right, 1, max(logical_width, 1))
    top = _clamp(top, 0, max(logical_height - 1, 0))
    bottom = _clamp(bottom, 1, max(logical_height, 1))

    return (left * scale_x, top * scale_y, right * scale_x, bottom * scale_y)


def save_go_to_element_debug_snapshot(
    ymin: float,
    xmin: float,
    ymax: float,
    xmax: float,
    target_description: str = "",
) -> str:
    """Save annotated debug image showing the bbox and its computed center."""
    image = _get_last_capture_image()
    if image is None:
        image = capture_active_window()

    context = _get_last_capture_context() or {}
    left_px, top_px, right_px, bottom_px = _bbox_to_capture_pixel_box(ymin, xmin, ymax, xmax)
    center_x = left_px + ((right_px - left_px) / 2.0)
    center_y = top_px + ((bottom_px - top_px) / 2.0)

    draw = ImageDraw.Draw(image)
    border_width = max(3, int(round(min(image.size) * 0.004)))
    draw.rectangle(
        [left_px, top_px, right_px, bottom_px],
        outline=(255, 64, 64),
        width=border_width,
    )
    cross = max(8, int(round(min(image.size) * 0.01)))
    draw.line([(center_x - cross, center_y), (center_x + cross, center_y)], fill=(64, 255, 64), width=border_width)
    draw.line([(center_x, center_y - cross), (center_x, center_y + cross)], fill=(64, 255, 64), width=border_width)

    mode = context.get("mode", "unknown")
    logical_width = context.get("logical_width", image.size[0])
    logical_height = context.get("logical_height", image.size[1])
    scale_x = context.get("scale_x", 1.0)
    scale_y = context.get("scale_y", 1.0)
    target = target_description.strip() if isinstance(target_description, str) and target_description.strip() else "target"
    text = (
        f"target={target} bbox=[{ymin},{xmin},{ymax},{xmax}] "
        f"mode={mode} logical={logical_width}x{logical_height} "
        f"image={image.size[0]}x{image.size[1]} scale=({scale_x:.2f},{scale_y:.2f})"
    )
    text_x = max(8, int(left_px))
    text_y = max(8, int(top_px) - 26)
    draw.rectangle([text_x - 4, text_y - 2, text_x + min(len(text) * 7, image.size[0] - text_x - 4), text_y + 18], fill=(0, 0, 0))
    draw.text((text_x, text_y), text, fill=(255, 255, 0))

    path = os.path.join("/tmp", f"cua_vision_bbox_debug_{int(time.time() * 1000)}.png")
    image.save(path)
    try:
        image.save("/tmp/cua_vision_bbox_debug_latest.png")
    except Exception:
        pass
    return path


def go_to_element(
    ymin: float,
    xmin: float,
    ymax: float,
    xmax: float,
    target_description: str = "",
):
    """
    Move cursor to the center of a target bounding box.

    The bbox should be in active-window coordinates (0-1000, 0-1, or pixels).
    """
    context = _get_last_capture_context()
    if not context:
        capture_active_window()
        context = _get_last_capture_context() or {}

    bbox_w, bbox_h = _bbox_logical_dimensions(ymin, xmin, ymax, xmax)
    target = target_description.strip() if isinstance(target_description, str) else "target"
    auto_zoom = _should_force_zoom(bbox_w, bbox_h)

    if auto_zoom:
        screenshot = _get_last_capture_image()
        if screenshot is None:
            screenshot = capture_active_window()
            context = _get_last_capture_context() or context
        offset = (
            float(context.get("offset_x", 0.0)),
            float(context.get("offset_y", 0.0)),
        )
        window_scale = (
            float(context.get("scale_x", 1.0)),
            float(context.get("scale_y", 1.0)),
        )
        result = crop_and_search_click(
            screenshot=screenshot,
            crop_bounds=(ymin, xmin, ymax, xmax),
            target_description=target,
            window_offset=offset,
            window_scale=window_scale,
            model_name=_get_precision_locator_model_name(),
            should_stop=is_stop_requested,
            perform_click=False,
            pad_pixels=FORCED_ZOOM_PAD_PX,
            rebalance_edges=True,
        )
        x, y = result["x"], result["y"]
    else:
        x, y = _bbox_center_to_screen_coords(ymin, xmin, ymax, xmax)

    context = _get_last_capture_context() or {}
    mode = context.get("mode", "unknown")
    logical_w = context.get("logical_width", context.get("width", "?"))
    logical_h = context.get("logical_height", context.get("height", "?"))
    scale_x = float(context.get("scale_x", 1.0))
    scale_y = float(context.get("scale_y", 1.0))
    move_cursor(x, y, duration=0.2)
    print(f"[VisionAgent] go_to_element centered on {target} at ({x:.1f}, {y:.1f})")
    print(
        "[VisionAgent] go_to_element context "
        f"mode={mode} logical={logical_w}x{logical_h} scale=({scale_x:.2f},{scale_y:.2f})"
    )
    print(
        "[VisionAgent] go_to_element bbox "
        f"size=({bbox_w:.1f}x{bbox_h:.1f}) auto_zoom={'on' if auto_zoom else 'off'}"
    )


# ================================================================================
# LEGACY FALLBACK LOCATOR
# ================================================================================

def find_and_click_element(type_of_click: str, element_description: str):
    """Backward-compatible wrapper for legacy element localization."""
    legacy_find_and_click_element(
        type_of_click,
        element_description,
        should_stop=is_stop_requested,
    )


def run_legacy_locator_fallback(type_of_click: str, element_description: str) -> bool:
    """Run legacy two-call locator as an internal fallback."""
    try:
        return bool(legacy_find_and_click_element(
            type_of_click,
            element_description,
            should_stop=is_stop_requested,
        ))
    except Exception as e:
        print(f"[LegacyLocator] Fallback failed: {e}")
        return False


def _get_precision_locator_model_name() -> str:
    """Get the model name used by the crop-and-search precision locator."""
    try:
        model_name = get_clovis_model()
        if isinstance(model_name, str) and model_name.strip():
            return model_name.strip()
    except Exception:
        pass
    return "gemini-3-flash-preview"


def crop_and_search(
    target_description: str,
    ymin: float,
    xmin: float,
    ymax: float,
    xmax: float,
):
    """
    Agentic vision precision tool.

    Crops a coarse region, runs second-pass target localization in that crop,
    and moves the cursor to the refined center.
    """
    if not isinstance(target_description, str) or not target_description.strip():
        raise ValueError("target_description is required for crop_and_search")

    screenshot = capture_active_window()
    context = _get_last_capture_context() or {}
    offset = (
        float(context.get("offset_x", 0.0)),
        float(context.get("offset_y", 0.0)),
    )
    window_scale = (
        float(context.get("scale_x", 1.0)),
        float(context.get("scale_y", 1.0)),
    )

    result = crop_and_search_click(
        screenshot=screenshot,
        crop_bounds=(ymin, xmin, ymax, xmax),
        target_description=target_description.strip(),
        window_offset=offset,
        window_scale=window_scale,
        model_name=_get_precision_locator_model_name(),
        should_stop=is_stop_requested,
        perform_click=False,
        pad_pixels=FORCED_ZOOM_PAD_PX,
        rebalance_edges=True,
    )
    move_cursor(result["x"], result["y"], duration=0.2)
    print(
        "[AgenticVision] crop_and_search positioned cursor for "
        f"{result['target_description']} at ({result['x']:.1f}, {result['y']:.1f})"
    )


# ================================================================================
# TOOL EXECUTION HELPERS
# ================================================================================

def _filter_tool_args(tool_name: str, args: dict) -> dict:
    tool = VISION_TOOL_MAP.get(tool_name)
    if tool is None:
        raise ValueError(f"Unknown tool: {tool_name}")

    signature = inspect.signature(tool)
    allowed = set(signature.parameters.keys())
    filtered = {}
    for key, value in (args or {}).items():
        if key in TOOL_METADATA_KEYS and key not in allowed:
            continue
        if key in allowed:
            filtered[key] = value
    return filtered


def execute_tool_call(tool_name: str, args: dict):
    """Execute a tool call while dropping UI metadata-only arguments."""
    tool = VISION_TOOL_MAP.get(tool_name)
    if tool is None:
        raise ValueError(f"Unknown tool: {tool_name}")

    filtered_args = _filter_tool_args(tool_name, args)
    tool(**filtered_args)


# ================================================================================
# TOOL DECLARATIONS FOR GEMINI
# ================================================================================

def _with_status_text(properties: dict) -> dict:
    enriched = dict(properties)
    enriched["status_text"] = {
        "type": "string",
        "description": "Short status text shown to the user while executing this action.",
    }
    return enriched


def _with_click_metadata(properties: dict) -> dict:
    enriched = _with_status_text(properties)
    enriched["target_description"] = {
        "type": "string",
        "description": "Short description of the click target (for retry fallback).",
    }
    return enriched


type_string_declaration = {
    "name": "type_string",
    "description": "Types out a string in the currently focused input. Optionally submit with Enter.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "string": {"type": "string", "description": "The string to type out."},
            "submit": {
                "type": "boolean",
                "description": "Set true to press Enter once after typing.",
            },
        }),
        "required": ["string"],
    },
}

press_ctrl_hotkey_declaration = {
    "name": "press_ctrl_hotkey",
    "description": "Press a control-style hotkey. On macOS this maps to Command automatically; on other OSes it uses Control.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "key": {"type": "string", "description": "The key to press with control."},
        }),
        "required": ["key"],
    },
}

press_alt_hotkey_declaration = {
    "name": "press_alt_hotkey",
    "description": "Press a key along with the alt key to emulate a hotkey.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "key": {"type": "string", "description": "The key to press with alt."},
        }),
        "required": ["key"],
    },
}

click_left_click_declaration = {
    "name": "click_left_click",
    "description": "Emulates a mouse left click at the current cursor position.",
    "parameters": {
        "type": "object",
        "properties": _with_click_metadata({}),
    },
}

click_double_left_click_declaration = {
    "name": "click_double_left_click",
    "description": "Emulates a mouse double left click at the current cursor position.",
    "parameters": {
        "type": "object",
        "properties": _with_click_metadata({}),
    },
}

click_right_click_declaration = {
    "name": "click_right_click",
    "description": "Emulates a mouse right click at the current cursor position.",
    "parameters": {
        "type": "object",
        "properties": _with_click_metadata({}),
    },
}

go_to_element_declaration = {
    "name": "go_to_element",
    "description": (
        "Move cursor to the center of a target bounding box."
    ),
    "parameters": {
        "type": "object",
        "properties": _with_click_metadata({
            "ymin": {
                "type": "number",
                "description": "Top edge of target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
            "xmin": {
                "type": "number",
                "description": "Left edge of target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
            "ymax": {
                "type": "number",
                "description": "Bottom edge of target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
            "xmax": {
                "type": "number",
                "description": "Right edge of target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
        }),
        "required": [
            "target_description",
            "ymin",
            "xmin",
            "ymax",
            "xmax",
        ],
    },
}

crop_and_search_declaration = {
    "name": "crop_and_search",
    "description": (
        "Optional precision cursor positioning helper. Provide a best-effort bounding box around a likely target; "
        "the tool pads the box, runs a second localization pass inside the crop, and moves cursor to the refined center."
    ),
    "parameters": {
        "type": "object",
        "properties": _with_click_metadata({
            "ymin": {
                "type": "number",
                "description": "Top edge of a best-effort target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
            "xmin": {
                "type": "number",
                "description": "Left edge of a best-effort target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
            "ymax": {
                "type": "number",
                "description": "Bottom edge of a best-effort target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
            "xmax": {
                "type": "number",
                "description": "Right edge of a best-effort target bounding box, normalized 0-1000 (or ratio 0-1).",
            },
        }),
        "required": [
            "target_description",
            "ymin",
            "xmin",
            "ymax",
            "xmax",
        ],
    },
}

hold_down_left_click_declaration = {
    "name": "hold_down_left_click",
    "description": "Emulates holding down the left mouse button.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "x": {"type": "number", "description": "X coordinate on screen."},
            "y": {"type": "number", "description": "Y coordinate on screen."},
        }),
        "required": ["x", "y"],
    },
}

release_left_click_declaration = {
    "name": "release_left_click",
    "description": "Emulates releasing the left mouse button.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "x": {"type": "number", "description": "X coordinate on screen."},
            "y": {"type": "number", "description": "Y coordinate on screen."},
        }),
        "required": ["x", "y"],
    },
}

press_key_for_duration_declaration = {
    "name": "press_key_for_duration",
    "description": "Holds down a key for a specified duration.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "key": {"type": "string", "description": "The key to press."},
            "seconds": {"type": "number", "description": "Duration in seconds."},
        }),
        "required": ["key", "seconds"],
    },
}

hold_down_key_declaration = {
    "name": "hold_down_key",
    "description": "Press down a key indefinitely until release_held_key is called.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "key": {"type": "string", "description": "The key to hold down."},
        }),
        "required": ["key"],
    },
}

release_held_key_declaration = {
    "name": "release_held_key",
    "description": "Release a previously held down key.",
    "parameters": {
        "type": "object",
        "properties": _with_status_text({
            "key": {"type": "string", "description": "The key to release."},
        }),
        "required": ["key"],
    },
}

remember_information_declaration = {
    "name": "remember_information",
    "description": "Remember/memorize information for later use. Use this when the user asks you to remember something.",
    "parameters": {
        "type": "object",
        "properties": {
            "thing_to_remember": {
                "type": "string",
                "description": "The information to remember, detailed enough to reproduce later.",
            },
        },
        "required": ["thing_to_remember"],
    },
}

tts_speak_declaration = {
    "name": "tts_speak",
    "description": "Verbally speak to the user. Use this to give feedback or confirmation.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to speak to the user."},
        },
        "required": ["text"],
    },
}

task_is_complete_declaration = {
    "name": "task_is_complete",
    "description": "Signal that the task is complete. This should be the final action.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Optional short completion message to speak.",
            },
        },
    },
}


# ================================================================================
# TOOL SETS
# ================================================================================

VISION_TOOLS = [types.Tool(function_declarations=[
    type_string_declaration,
    press_ctrl_hotkey_declaration,
    press_alt_hotkey_declaration,
    go_to_element_declaration,
    click_left_click_declaration,
    click_double_left_click_declaration,
    click_right_click_declaration,
    crop_and_search_declaration,
    hold_down_left_click_declaration,
    release_left_click_declaration,
    press_key_for_duration_declaration,
    hold_down_key_declaration,
    release_held_key_declaration,
    remember_information_declaration,
    task_is_complete_declaration,
    tts_speak_declaration,
])]

VISION_TOOL_MAP = {
    "type_string": type_string,
    "press_ctrl_hotkey": press_ctrl_hotkey,
    "press_alt_hotkey": press_alt_hotkey,
    "go_to_element": go_to_element,
    "click_left_click": click_left_click,
    "click_double_left_click": click_double_left_click,
    "click_right_click": click_right_click,
    "crop_and_search": crop_and_search,
    "hold_down_left_click": hold_down_left_click,
    "hold_down_right_click": hold_down_right_click,
    "release_left_click": release_left_click,
    "release_right_click": release_right_click,
    "press_key_for_duration": press_key_for_duration,
    "hold_down_key": hold_down_key,
    "release_held_key": release_held_key,
    "remember_information": remember_information,
    "task_is_complete": task_is_complete,
    "tts_speak": tts_speak,
    "find_and_click_element": find_and_click_element,
}

TOOL_CONFIG = types.ToolConfig(
    function_calling_config=types.FunctionCallingConfig(
        mode="ANY",
    )
)
