"""Support for Snoo Device."""
from .pysnoo.const import (
    MANUFACTURER
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_VIBRATION,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SNOO_COORDINATOR, SNOO_GATEWAY


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up snoo covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    snoo = data[SNOO_GATEWAY]
    coordinator = data[SNOO_COORDINATOR]

    entities = []

    for device in snoo.devices.values():
        entities.append(SnooBinarySensorEntity(coordinator, device))

    async_add_entities(entities, True)


class SnooBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Snoo device."""

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        super().__init__(coordinator)
        self._device = device

    @property
    def device_class(self):
        """We track connectivity for device."""
        return DEVICE_CLASS_VIBRATION

    @property
    def name(self):
        """Return the name of the device if any."""
        return f"{self._device.name}"

    @property
    def is_on(self):
        """Return if the device is online."""
        return self._device.is_on

    @property
    def available(self) -> bool:
        """Entity is always available."""
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
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "sw_version": self._device.firmware_version,
        }
        return device_info
