from ui.visualization_api.client import get_client
from core.registry import clear

def _build_payload():
  return {"command": "clear"}


async def _clear_screen():
  """
  Clear all visual elements on screen.

  Args:
      host (str, optional): Server host. Defaults to "127.0.0.1".
      port (int, optional): Server port. Defaults to 8765.
  """
  payload = _build_payload()
  client = await get_client()
  await client.send(payload)
  clear()
