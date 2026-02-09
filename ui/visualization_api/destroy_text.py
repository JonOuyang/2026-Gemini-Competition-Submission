from ui.visualization_api.client import get_client
from core.registry import remove_entry


def _build_payload(text_id):
  return {"command": "remove_text", "id": text_id}


async def _destroy_text(text_id: str):
  """
  Remove a text label from screen.

  Args:
    text_id (str): ID returned by create_text
  """
  payload = _build_payload(text_id)
  client = await get_client()
  await client.send(payload)
  remove_entry(text_id)
