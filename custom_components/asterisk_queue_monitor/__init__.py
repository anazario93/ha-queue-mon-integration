"""Asterisk Queue Monitor integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PLATFORMS, CONF_REFRESH_INTERVAL, CONF_SECRET, DEFAULT_REFRESH_INTERVAL
from .ami import AmiClient

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML (config flow is preferred)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Asterisk Queue Monitor from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 5038)
    username = entry.data[CONF_USERNAME]
    secret = entry.data.get(CONF_SECRET, entry.data.get(CONF_PASSWORD))
    interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

    client = AmiClient(host, port, username, secret)
    coordinator = QueueCoordinator(hass, client, interval, entry.entry_id)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await client.async_close()
        raise ConfigEntryNotReady(f"Unable to connect to Asterisk AMI: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.async_close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


class QueueCoordinator(DataUpdateCoordinator):
    """Fetch queue snapshots and maintain event-derived counters."""

    def __init__(self, hass, client: AmiClient, interval: int, entry_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(seconds=max(1, int(interval))),
        )
        self.client = client
        self.abandoned_calls = 0
        self.last_event = None
        client.add_event_listener(self._handle_event)

    def _handle_event(self, event: dict) -> None:
        """Track counters from unsolicited AMI events."""
        event_name = event.get("Event")
        if not event_name:
            return
        self.last_event = event_name
        # QueueStatus snapshots provide authoritative counters and live state.

    async def _async_update_data(self) -> dict:
        """Get an authoritative QueueStatus snapshot."""
        try:
            events = await self.client.async_queue_status()
        except Exception as err:
            raise UpdateFailed(f"AMI QueueStatus failed: {err}") from err

        queues: dict[str, dict] = {}
        for event in events:
            kind = event.get("Event", "")
            queue = event.get("Queue")
            if not queue:
                continue
            state = queues.setdefault(queue, {"callers": [], "members": [], "abandoned_calls": 0})
            if kind == "QueueParams":
                state["abandoned_calls"] = _int(event.get("Abandoned"), 0)
            elif kind == "QueueEntry":
                state["callers"].append({
                    "queue": queue,
                    "position": _int(event.get("Position"), 0),
                    "caller_id": event.get("CallerIDNum", "Unknown"),
                    "caller_name": event.get("CallerIDName", ""),
                    "channel": event.get("Channel", ""),
                    "unique_id": event.get("Uniqueid", ""),
                    "wait_seconds": _int(event.get("Wait"), 0),
                })
            elif kind == "QueueMember":
                state["members"].append({
                    "name": event.get("Name", event.get("Location", "Unknown")),
                    "interface": event.get("Location", event.get("Interface", "")),
                    "status": _int(event.get("Status"), -1),
                    "paused": str(event.get("Paused", "0")).lower() in ("1", "true", "yes"),
                    "in_call": str(event.get("InCall", "0")).lower() in ("1", "true", "yes"),
                    "calls_taken": _int(event.get("CallsTaken"), 0),
                    "last_call": _int(event.get("LastCall"), 0),
                })

        callers = []
        members = []
        for queue_name, state in queues.items():
            callers.extend(state["callers"])
            members.extend([{**member, "queue": queue_name} for member in state["members"]])
        callers.sort(key=lambda item: (item["queue"].lower(), item["position"]))
        # Aggregate agent metrics by unique interface, not queue membership.
        # An agent assigned to several queues must only count once globally.
        unique_members: dict[str, dict] = {}
        for member in members:
            identity = (member.get("interface") or member.get("name") or "").strip().lower()
            if not identity:
                identity = member["queue"].lower() + ":unknown"
            current = unique_members.get(identity)
            # Prefer a record showing the agent is busy/paused over an
            # available record from another queue.
            if current is None or member["paused"] or member["in_call"] or member["status"] != 1:
                unique_members[identity] = member

        # Asterisk member status 1 means not in use. Paused or in-call members
        # must not be counted as available.
        available = sum(
            1 for member in unique_members.values()
            if member["status"] == 1 and not member["paused"] and not member["in_call"]
        )
        abandoned_calls = sum(state["abandoned_calls"] for state in queues.values())
        return {
            "queues": queues,
            "callers": callers,
            "members": members,
            "unique_members": list(unique_members.values()),
            "waiting_calls": len(callers),
            "available_agents": available,
            "abandoned_calls": abandoned_calls,
            "last_event": self.last_event,
            "connected": self.client.connected,
        }


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
