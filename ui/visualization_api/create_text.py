import uuid
from typing import Optional

from ui.visualization_api.client import get_client
from ui.visualization_api.draw_bounding_box import get_box_rect
from core.registry import register_text


def _normalize_source(source: Optional[str]) -> str:
  if isinstance(source, str) and source.strip():
    return source.strip()
  return "unknown"


def _log_text(channel: str, text_id: str, text: str, source: Optional[str] = None):
  safe_text = "" if text is None else str(text)
  src = _normalize_source(source)
  print(f"[UI_TEXT][{src}][{channel}][{text_id}] {safe_text}")


def _build_payload(x, y, text, text_id, font_size, font_family, align, baseline, source):
  payload = {
    "command": "draw_text",
    "id": text_id,
    "x": x,
    "y": y,
    "text": text,
    "fontSize": font_size,
    "fontFamily": font_family,
    "align": align,
    "baseline": baseline,
  }
  if source is not None:
    payload["source"] = _normalize_source(source)
  return payload


async def _create_text(
  x: int,
  y: int,
  text: str,
  text_id: str,
  font_size: int,
  font_family: str,
  align: str,
  baseline: str,
  source: Optional[str] = None,
):
  """
  Draw a text label on screen.

  Args:
    x (int): X coordinate (pixels)
    y (int): Y coordinate (pixels)
    text (str): Label text
    text_id (str, optional): Unique ID for the text label
    font_size (int, optional): Font size in px
    font_family (str, optional): Font family name
    align (str, optional): Canvas textAlign value
    baseline (str, optional): Canvas textBaseline value
  """
  text_id = text_id or f"text_{uuid.uuid4().hex[:8]}"
  _log_text("draw_text", text_id, text, source)
  payload = _build_payload(
    x,
    y,
    text,
    text_id,
    font_size,
    font_family,
    align,
    baseline,
    source,
  )
  client = await get_client()
  await client.send(payload)
  register_text(text_id, payload["x"], payload["y"])
  return text_id


async def _create_text_for_box(
  box: dict,
  text: str,
  position: str,
  text_id: str,
  font_size: int,
  font_family: str,
  align: str,
  padding: int,
  source: Optional[str] = None,
):
  """
  Draw a text label relative to a bounding box.

  Args:
    box (dict): {"x": int, "y": int, "width": int, "height": int}
    text (str): Label text
    position (str, optional): "top", "bottom", "left", or "right"
    text_id (str, optional): Unique ID for the text label
    font_size (int, optional): Font size in px
    font_family (str, optional): Font family name
    align (str, optional): Canvas textAlign value for the anchor
    padding (int, optional): Pixels between text and box
  """
  x = box["x"]
  y = box["y"]
  width = box["width"]
  height = box["height"]

  center_x = x + (width / 2)
  center_y = y + (height / 2)

  if position == "top":
    anchor_x = center_x
    anchor_y = y - padding
    baseline = "bottom"
    default_align = "center"
  elif position == "bottom":
    anchor_x = center_x
    anchor_y = y + height + padding
    baseline = "top"
    default_align = "center"
  elif position == "left":
    anchor_x = x - padding
    anchor_y = center_y
    baseline = "middle"
    default_align = "right"
  elif position == "right":
    anchor_x = x + width + padding
    anchor_y = center_y
    baseline = "middle"
    default_align = "left"
  else:
    raise ValueError("position must be one of: top, bottom, left, right")

  anchor_align = align or default_align
  return await _create_text(
    int(anchor_x),
    int(anchor_y),
    text,
    text_id=text_id,
    font_size=font_size,
    font_family=font_family,
    align=anchor_align,
    baseline=baseline,
    source=source,
  )


async def _create_text_for_box_id(
  box_id: str,
  text: str,
  position: str,
  text_id: str,
  font_size: int,
  font_family: str,
  align: str,
  padding: int,
  source: Optional[str] = None,
):
  """
  Draw a text label relative to a cached bounding box ID.

  Args:
    box_id (str): ID returned by draw_bounding_box
    text (str): Label text
    position (str, optional): "top", "bottom", "left", or "right"
    text_id (str, optional): Unique ID for the text label
    font_size (int, optional): Font size in px
    font_family (str, optional): Font family name
    align (str, optional): Canvas textAlign value for the anchor
    padding (int, optional): Pixels between text and box
  """
  box = get_box_rect(box_id)
  if not box:
    raise ValueError(f"box_id not found in cache: {box_id}")
  return await _create_text_for_box(
    box,
    text,
    position=position,
    text_id=text_id,
    font_size=font_size,
    font_family=font_family,
    align=align,
    padding=padding,
    source=source,
  )
