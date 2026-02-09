from ui.visualization_api.client import get_client
from ui.visualization_api.draw_bounding_box import forget_box_rect
from core.registry import remove_entry


async def _destroy_box(box_id: str):
  forget_box_rect(box_id)
  payload = {
    "command": "remove_box",
    "id": box_id
  }

  client = await get_client()
  await client.send(payload)
  remove_entry(box_id)
