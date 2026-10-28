"""Sensors for Asterisk Queue Monitor."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import QueueCoordinator
from .const import (
    DOMAIN,
    SENSOR_WAITING_CALLS,
    SENSOR_AVAILABLE_AGENTS,
    SENSOR_WAITING_CALLERS,
    SENSOR_ABANDONED_CALLS,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: QueueCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        QueueSensor(coordinator, entry, SENSOR_WAITING_CALLS),
        QueueSensor(coordinator, entry, SENSOR_AVAILABLE_AGENTS),
        QueueSensor(coordinator, entry, SENSOR_WAITING_CALLERS),
        QueueSensor(coordinator, entry, SENSOR_ABANDONED_CALLS),
    ])


class QueueSensor(CoordinatorEntity, SensorEntity):
    """A sensor backed by the queue coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: QueueCoordinator, entry: ConfigEntry, sensor_type: str) -> None:
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Asterisk Queue Monitor",
            "manufacturer": "Asterisk",
            "model": "Queue Monitor",
        }
        names = {
            SENSOR_WAITING_CALLS: ("Waiting Calls", "mdi:phone-clock", "calls"),
            SENSOR_AVAILABLE_AGENTS: ("Available Agents", "mdi:account-headset", "agents"),
            SENSOR_WAITING_CALLERS: ("Waiting Callers", "mdi:format-list-bulleted", None),
            SENSOR_ABANDONED_CALLS: ("Abandoned Calls", "mdi:phone-missed", "calls"),
        }
        name, icon, unit = names[sensor_type]
        self._attr_name = name
        self._attr_icon = icon
        if unit:
            self._attr_native_unit_of_measurement = unit
        if sensor_type in (SENSOR_WAITING_CALLS, SENSOR_AVAILABLE_AGENTS, SENSOR_ABANDONED_CALLS):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING if sensor_type == SENSOR_ABANDONED_CALLS else SensorStateClass.MEASUREMENT
        if sensor_type == SENSOR_ABANDONED_CALLS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return {
            SENSOR_WAITING_CALLS: data.get("waiting_calls", 0),
            SENSOR_AVAILABLE_AGENTS: data.get("available_agents", 0),
            SENSOR_WAITING_CALLERS: len(data.get("callers", [])),
            SENSOR_ABANDONED_CALLS: data.get("abandoned_calls", 0),
        }[self._sensor_type]

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self._sensor_type == SENSOR_WAITING_CALLS:
            return {
                "queues": {name: len(state["callers"]) for name, state in data.get("queues", {}).items()},
                "callers": data.get("callers", []),
            }
        if self._sensor_type == SENSOR_AVAILABLE_AGENTS:
            return {
                "members": data.get("members", []),
                "paused_agents": sum(1 for member in data.get("members", []) if member["paused"]),
                "total_agents": len(data.get("members", [])),
            }
        if self._sensor_type == SENSOR_WAITING_CALLERS:
            return {
                "callers": data.get("callers", []),
                "queues": list(data.get("queues", {}).keys()),
            }
        return {"last_event": data.get("last_event"), "connected": data.get("connected", False)}
