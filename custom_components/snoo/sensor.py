"""Support for Snoo devices."""
from pysnooapi.const import (
    MANUFACTURER
)

from homeassistant.components.cover import (
    Entity
)
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPENING
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SNOO_COORDINATOR,
    SNOO_GATEWAY
)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up snoo sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    snoo = data[SNOO_GATEWAY]
    coordinator = data[SNOO_COORDINATOR]

    async_add_entities(
        [SnooDevice(coordinator, device) for device in snoo.devices.values()], True
    )


class SnooDevice(CoordinatorEntity, Entity):
    """Representation of a Snoo device."""

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        super().__init__(coordinator)
        self._device = device

    @property
    def name(self):
        """Return the name of the snoo device if any."""
        return self._device.name

    @property
    def available(self):
        """Return if the device is online."""
        return self._device.is_online

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device.device_id

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "sw_version": self._device.firmware_version,
        }
        return device_info

    @property
    def state(self):
        """Return the name of the sensor."""
        return self._device.state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        res = {}
        res["session"] = self._device.session
        return res

    @property
    def icon(self):
        """Return the icon of the switch."""
        return "mdi:baby-face" if self._device.is_on else "mdi:baby-face-outline"

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
