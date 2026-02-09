import uuid

from ui.visualization_api.client import get_client


async def _draw_dot(
  x: int,
  y: int,
  dot_id: str,
  radius: int,
  dot_color: str,
  ring_color: str,
  line_target_text_id: str = None,
  ring_radius: int = None,
):
  """
  Draw a dot on screen with optional line to a text element.
  Line is always thin white (#ffffff, width 2) - not configurable.

  Args:
    x (int): X coordinate (pixels)
    y (int): Y coordinate (pixels)
    dot_id (str): Unique ID for the dot
    radius (int): Dot radius in px
    dot_color (str): Dot fill color
    ring_color (str): Ring color
    line_target_text_id (str, optional): Text id to draw line to
  """
  dot_id = dot_id or f"dot_{uuid.uuid4().hex[:8]}"
  payload = {
    "command": "draw_dot",
    "id": dot_id,
    "x": int(x),
    "y": int(y),
    "radius": int(radius),
    "color": dot_color,
    "dotColor": dot_color,
    "ringColor": ring_color,
  }
  if ring_radius is not None:
    payload["ringRadius"] = int(ring_radius)
  # Line is always thin white - hardcoded
  if line_target_text_id is not None:
    payload["lineTargetTextId"] = line_target_text_id
    payload["lineColor"] = "#ffffff"
    payload["lineWidth"] = 2
  client = await get_client()
  await client.send(payload)
  return dot_id
