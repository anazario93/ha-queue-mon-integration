"""Small asynchronous Asterisk Manager Interface (AMI) client."""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)


def _parse_packet(raw: bytes) -> dict[str, str]:
    """Parse an AMI header packet."""
    result: dict[str, str] = {}
    for line in raw.decode("utf-8", errors="replace").split("\r\n"):
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


class AmiClient:
    """Persistent AMI TCP client with QueueStatus snapshots."""

    def __init__(self, host: str, port: int, username: str, secret: str | None) -> None:
        self.host = host
        self.port = int(port)
        self.username = username
        self.secret = secret or ""
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._listeners: list[Callable[[dict], None]] = []
        self._snapshot_events: dict[str, list[dict]] = {}
        self._snapshot_futures: dict[str, asyncio.Future] = {}
        self._completion_events: set[str] = set()
        self._ids = itertools.count(1)
        self.connected = False
        self._connect_lock = asyncio.Lock()

    def add_event_listener(self, listener: Callable[[dict], None]) -> None:
        self._listeners.append(listener)

    async def async_connect(self) -> None:
        """Connect and log in, creating the reader task."""
        async with self._connect_lock:
            if self.connected and self.writer and not self.writer.is_closing():
                return
            await self._close_socket()
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            # Read the initial AMI banner before sending Login.
            await asyncio.wait_for(self.reader.readline(), timeout=5)
            self._reader_task = asyncio.create_task(self._reader_loop(), name="asterisk-ami-reader")
            response = await self._send_action({
                "Action": "Login",
                "Username": self.username,
                "Secret": self.secret,
                "Events": "on",
            }, completion="Response")
            if response.get("Response", "").lower() != "success":
                await self._close_socket()
                raise ConnectionError(response.get("Message", "AMI login failed"))
            self.connected = True

    async def async_queue_status(self) -> list[dict]:
        """Return QueueStatus events for all queues."""
        if not self.connected:
            await self.async_connect()
        action_id = str(next(self._ids))
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._snapshot_events[action_id] = []
        self._snapshot_futures[action_id] = future
        self._completion_events.add(action_id)
        try:
            await self._write_packet({"Action": "QueueStatus", "ActionID": action_id})
            return await asyncio.wait_for(future, timeout=15)
        except Exception:
            raise
        finally:
            self._snapshot_events.pop(action_id, None)
            self._snapshot_futures.pop(action_id, None)
            self._completion_events.discard(action_id)

    async def _send_action(self, fields: dict[str, str], completion: str) -> dict:
        """Send an action and wait for a matching response packet."""
        action_id = str(next(self._ids))
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._snapshot_futures[action_id] = future
        self._snapshot_events[action_id] = []
        await self._write_packet({**fields, "ActionID": action_id})
        try:
            packets = await asyncio.wait_for(future, timeout=10)
            if isinstance(packets, list):
                return next((packet for packet in packets if packet.get("Response")), {})
            return packets
        finally:
            self._snapshot_futures.pop(action_id, None)
            self._snapshot_events.pop(action_id, None)

    async def _write_packet(self, fields: dict[str, str]) -> None:
        if not self.writer or self.writer.is_closing():
            raise ConnectionError("AMI socket is not connected")
        payload = "".join(f"{key}: {value}\r\n" for key, value in fields.items()) + "\r\n"
        self.writer.write(payload.encode())
        await self.writer.drain()

    async def _reader_loop(self) -> None:
        """Read AMI packets and dispatch events until disconnected."""
        try:
            while self.reader:
                raw = await self.reader.readuntil(b"\r\n\r\n")
                packet = _parse_packet(raw)
                action_id = packet.get("ActionID")
                if action_id and action_id in self._snapshot_events:
                    self._snapshot_events[action_id].append(packet)
                for listener in tuple(self._listeners):
                    try:
                        listener(packet)
                    except Exception:
                        _LOGGER.exception("AMI event listener failed")
                event = packet.get("Event", "")
                future = self._snapshot_futures.get(action_id or "")
                if future and not future.done():
                    if event == "QueueStatusComplete":
                        future.set_result(self._snapshot_events.get(action_id, []))
                    elif packet.get("Response") and packet.get("Response", "").lower() != "success":
                        future.set_exception(ConnectionError(packet.get("Message", "AMI action failed")))
                    elif packet.get("Response") and packet.get("Response", "").lower() == "success":
                        # QueueStatus emits a success response before its events;
                        # wait for QueueStatusComplete for snapshot actions.
                        if action_id not in self._completion_events:
                            future.set_result(packet)
        except asyncio.CancelledError:
            raise
        except (asyncio.IncompleteReadError, ConnectionError, OSError, asyncio.LimitOverrunError) as err:
            _LOGGER.warning("AMI connection lost: %s", err)
        finally:
            self.connected = False
            for future in self._snapshot_futures.values():
                if not future.done():
                    future.set_exception(ConnectionError("AMI connection closed"))

    async def _close_socket(self) -> None:
        if self._reader_task and self._reader_task is not asyncio.current_task():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
        self._reader_task = None
        self.connected = False
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (OSError, ConnectionError):
                pass
        self.reader = None
        self.writer = None

    async def async_close(self) -> None:
        """Close the AMI connection."""
        await self._close_socket()
