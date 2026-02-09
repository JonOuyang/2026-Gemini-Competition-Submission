import uuid
from typing import Optional

from ui.visualization_api.client import get_client
from core.registry import register_box

_BOX_CACHE = {}

def _build_payload(x, y, width, height, box_id, stroke, stroke_width, opacity, auto_contrast, fill):
  payload = {
    "command": "draw_box",
    "id": box_id,
    "x": int(x),
    "y": int(y),
    "width": int(width),
    "height": int(height),
    "strokeWidth": stroke_width,
    "opacity": opacity,
  }
  if stroke is not None:
    payload["stroke"] = stroke
  if fill is not None:
    payload["fill"] = fill
  if auto_contrast:
    payload["autoContrast"] = True

  return payload


def get_box_rect(box_id: str):
  box = _BOX_CACHE.get(box_id)
  if not box:
    return None
  return {
    "x": box["x"],
    "y": box["y"],
    "width": box["width"],
    "height": box["height"],
  }


def forget_box_rect(box_id: str):
  _BOX_CACHE.pop(box_id, None)


# Note that this is Google Gemini convention, which uses [y_min, x_min, y_max, x_max]
async def _draw_bounding_box(
  y_min: int,
  x_min: int,
  y_max: int,
  x_max: int,
  box_id: int,
  stroke: str,
  stroke_width: int,
  opacity: float,
  auto_contrast: bool = False,
  fill: Optional[str] = None,
):
  """
  Draw a bounding box on screen using Gemini-style coordinates (y_min, x_min, y_max, x_max).

  Args:
      y_min (int/float): Top edge coordinate.
      x_min (int/float): Left edge coordinate.
      y_max (int/float): Bottom edge coordinate.
      x_max (int/float): Right edge coordinate.
      box_id (str, optional): Unique ID for the box. Defaults to random UUID.
      stroke (str, optional): Color hex code. Defaults to "#73e331".
      stroke_width (int, optional): Width of the border. Defaults to 5.
      opacity (float, optional): Opacity of the box. Defaults to 0.8.
      host (str, optional): Server host. Defaults to "127.0.0.1".
      port (int, optional): Server port. Defaults to 8765.

  Returns:
      str: The box_id used.
  """
  width = x_max - x_min
  height = y_max - y_min
  
  box_id = box_id or f"box_{uuid.uuid4().hex[:8]}"
  
  payload = _build_payload(x_min, y_min, width, height, box_id, stroke, stroke_width, opacity, auto_contrast, fill)
  _BOX_CACHE[box_id] = {
    "x": payload["x"],
    "y": payload["y"],
    "width": payload["width"],
    "height": payload["height"],
  }
  client = await get_client()
  await client.send(payload)
  register_box(box_id, payload["x"], payload["y"], payload["x"] + payload["width"], payload["y"] + payload["height"])

  return box_id
