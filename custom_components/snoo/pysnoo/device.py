"""Define Snoo device."""
import logging
from datetime import datetime
from .utils import parse_datetime
from typing import TYPE_CHECKING, Optional, List, Dict, Any

from .const import WAIT_TIMEOUT
from .errors import RequestError, SnooError

if TYPE_CHECKING:
    from .api import API

_LOGGER = logging.getLogger(__name__)


class SnooDevice:
    """Define a snoo device."""

    def __init__(
        self, api: "API", device_json: dict, account: str, baby_json: dict
    ) -> None:
        """Initialize.
        :type account: str
        """
        self._api = api  # type: "API"
        self._account = account  # type: str
        self._device = self.parse_dates_device(device_json)  # type: dict
        self._baby = baby_json  # type: dict
        self._config = None
        self._session = None
        # self._device_state_update = device_state_update  # type: datetime

    @property
    def is_online(self) -> bool:
        """Return if device is online"""
        return self._config.get("networkStatus").get("isOnline") if self._config != None else False

    @property
    def is_on(self) -> bool:
        return self._session.get("startTime") != None and self._session.get("endTime") == None

    @property
    def last_update(self) -> datetime:
        """Return device's last state update timestamp"""
        return self._device.get("updatedAt")

    @property
    def device_state_update(self) -> str:
        """Return device's last state update timestamp"""
        return self._device_state_update

    @device_state_update.setter
    def device_state_update(self, value: datetime) -> None:
        self._device_state_update = value

    @property
    def api(self) -> "API":
        return self._api

    @property
    def account(self) -> str:
        """Return account associated with device"""
        return self._account

    @property
    def device_id(self) -> str:
        """Return the device ID (serial number)."""
        return self._device.get("serialNumber")

    @property
    def firmware_version(self) -> Optional[str]:
        """Return the firmware version for the device."""
        return self._device.get("firmwareVersion")

    @property
    def baby_id(self) -> Optional[str]:
        """Return the baby id."""
        return self._device.get("baby")

    @property
    def baby_name(self) -> Optional[str]:
        """Return the baby name"""
        return self._baby.get("babyName") if self._baby != None else None

    @property
    def name(self) -> bool:
        """Return the device name.
        Combination of baby name and device serial number because it's not clear if multiple devices can be assigned to same baby."""
        return f"{self.baby_name or self.baby_id}'s Snoo"

    @property
    def state(self) -> Optional[str]:
        """Returns the state of the device
           The API returns ONLINE, BASELINE, LEVEL1, LEVEL2, LEVEL3 and LEVEL4.
        """
        if self._session.get("startTime") != None and self._session.get("endTime") == None:
            return self._session.get("levels")[-1].get("level")
        else:
            return "ONLINE" if self.is_online else "OFFLINE"

    @property
    def baby(self) -> Optional[dict]:
        """Get the baby details for the device."""
        return self._baby

    @property
    def session(self) -> Optional[dict]:
        """Get the session details for the device."""
        return self._session

    @session.setter
    def session(self, value: dict) -> None:
        """Set the session details for the device."""
        self._session = self.parse_dates_session(value)

    def parse_dates_session(self, session: dict) -> dict:
        session['startTime'] = parse_datetime(session['startTime'])
        session['endTime'] = parse_datetime(session['endTime'])
        return session

    # def localize_date(self, dt: str) -> datetime:
    #     timezone = pytz.timezone(self._device.get("timezone"))
    #     tz_dt = timezone.localize(dt)
    #     utc_dt = pytz.utc.localize(tz_dt)
    #     return utc_dt

    @property
    def config(self) -> Optional[dict]:
        """Get the config details for the device."""
        return self._config

    @config.setter
    def config(self, value: dict) -> None:
        """Set the config details for the device."""
        self._config = self.parse_dates_config(value)

    def parse_dates_config(self, config: dict) -> dict:
        config['networkStatus']['lastPresence'] = parse_datetime(config['networkStatus']['lastPresence'])
        config['networkStatus']['lastProvisionSuccess'] = parse_datetime(config['networkStatus']['lastProvisionSuccess'])
        config['networkStatus']['lastSSID']['updatedAt'] = parse_datetime(config['networkStatus']['lastSSID']['updatedAt'])
        return config

    @property
    def device(self) -> Optional[dict]:
        """Get the device details for the device."""
        return self._device

    @device.setter
    def device(self, value: dict) -> None:
        """Set the device details for the device."""
        self._device = self.parse_dates_device(value)

    def parse_dates_device(self, device: dict) -> dict:
        device['createdAt'] = parse_datetime(device['createdAt'])
        device['updatedAt'] = parse_datetime(device['updatedAt'])
        device['lastProvisionSuccess'] = parse_datetime(device['lastProvisionSuccess'])
        device['firmwareUpdateDate'] = parse_datetime(device['firmwareUpdateDate'])
        device['lastSSID']["updatedAt"] = parse_datetime(device['lastSSID']["updatedAt"])
        return device

    @property
    def device_state(self) -> Optional[str]:
        return None

    async def update(self) -> None:
        """Get the latest info for this device."""
        await self._api.update_device_info()
