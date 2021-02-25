"""Define Snoo device."""
import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from .const import WAIT_TIMEOUT
from .errors import RequestError, SnooError

if TYPE_CHECKING:
    from .api import API

_LOGGER = logging.getLogger(__name__)


class SnooSession:
    """Define a session."""

    def __init__(
        self, api: "API", session_json: session_json, state_update: datetime
    ) -> None:
        """Initialize.
        :type account: str
        """
        self._api = api  # type: "API"
        self._session = session_json  # type: str
        self.state_update = state_update  # type: datetime


    @property
    def state(self) -> Optional[str]:
        # return self._device_state or self.device_state
        if self._session.get("startTime") != None and self._session.get("endTime") == None:
            return self._session.get("levels")[0].get("level")
        else:
            return None

    @property
    def session(self) -> Optional[dict]:
        """Get the session details for the device."""
        return self._session

    # @property
    # def device_state(self) -> Optional[str]:
    #     return None

    async def update(self) -> None:
        """Get the latest session info for this account."""
        await self._api._get_session_for_account()
