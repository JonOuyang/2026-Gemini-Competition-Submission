import asyncio
import json

import websockets

from core.settings import get_host, get_port


class VisualizationClient:
  def __init__(self):
    self._socket = None
    self._lock = asyncio.Lock()

  def _is_closed(self):
    if self._socket is None:
      return True
    closed = getattr(self._socket, "closed", None)
    if closed is not None:
      return closed
    state = getattr(self._socket, "state", None)
    if state is None:
      return False
    try:
      from websockets.protocol import State
    except Exception:
      return False
    return state is State.CLOSED

  async def _connect(self):
    host, port = get_host(), get_port()
    uri = f"ws://{host}:{port}"
    # Disable ping_interval since this client only sends (never receives),
    # so ping responses would never be processed and would cause timeouts
    self._socket = await websockets.connect(uri, ping_interval=None)

  async def send(self, payload):
    async with self._lock:
      if self._is_closed():
        await self._connect()
      await self._socket.send(json.dumps(payload))

  async def close(self):
    async with self._lock:
      if self._socket and not self._is_closed():
        await self._socket.close()


_client = None


async def get_client():
  global _client
  if _client is None:
    _client = VisualizationClient()
  return _client
