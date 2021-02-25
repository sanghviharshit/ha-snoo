"""Define the Snoo API."""
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Union, Tuple

from aiohttp import ClientSession, ClientResponse
from aiohttp.client_exceptions import ClientError, ClientResponseError

from .const import (
  BASE_ENDPOINT,
  LOGIN_URI,
  REFRESH_URI,
  DEVICES_URI,
  BABY_URI,
  DEVICE_CONFIGS_URI,
  ACCOUNT_URI,
  SESSION_URI,
  SESSION_STATS_DAILY_URI,
  SESSION_STATS_AVG_URI
)
from .device import SnooDevice
from .errors import AuthenticationError, InvalidCredentialsError, RequestError
from .request import SnooRequest, REQUEST_METHODS

_LOGGER = logging.getLogger(__name__)

DEFAULT_SESSION_UPDATE_INTERVAL = timedelta(seconds=5)
DEFAULT_DEVICE_UPDATE_INTERVAL = timedelta(seconds=120)

DEFAULT_TOKEN_REFRESH = 1 * 60 * 60  # 1 hour (api returns 3 hours)


class API:  # pylint: disable=too-many-instance-attributes
    """Define a class for interacting with the Snoo API."""

    def __init__(
        self, username: str, password: str, websession: ClientSession = None
    ) -> None:
        """Initialize."""
        self.__credentials = {"username": username, "password": password}
        self._snoorequests = SnooRequest(websession or ClientSession())
        self._authentication_task = None  # type:Optional[asyncio.Task]
        self._invalid_credentials = False  # type: bool
        self._lock = asyncio.Lock()  # type: asyncio.Lock
        self._update = asyncio.Lock()  # type: asyncio.Lock
        self._security_token = (
            None,
            None,
            None,
            None
        )  # type: Tuple[Optional[str], Optional[datetime], Optional[datetime]]

        self.account = None  # type: Dict
        self.baby = None # type: Dict
        self.devices = {}  # type: Dict[str, SnooDevice]
        self.last_state_update = None  # type: Optional[datetime]

    @property
    def username(self) -> str:
        return self.__credentials["username"]

    @username.setter
    def username(self, username: str) -> None:
        self._invalid_credentials = False
        self.__credentials["username"] = username

    @property
    def password(self) -> None:
        return None

    @password.setter
    def password(self, password: str) -> None:
        self._invalid_credentials = False
        self.__credentials["password"] = password

    async def request(
        self,
        method: str,
        returns: str,
        url: str,
        websession: ClientSession = None,
        headers: dict = None,
        params: dict = None,
        data: dict = None,
        json: dict = None,
        allow_redirects: bool = True,
        login_request: bool = False,
    ) -> Tuple[ClientResponse, Union[dict, str, None]]:
        """Make a request."""

        # Determine the method to call based on what is to be returned.
        call_method = REQUEST_METHODS.get(returns)
        if call_method is None:
            raise RequestError(f"Invalid return object requested: {returns}")

        call_method = getattr(self._snoorequests, call_method)

        # if this is a request as part of authentication to have it go through in parallel.
        if login_request:
            try:
                return await call_method(
                    method=method,
                    url=url,
                    websession=websession,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    allow_redirects=allow_redirects,
                )
            except ClientResponseError as err:
                message = (
                    f"Error requesting data from {url}: {err.status} - {err.message}"
                )
                _LOGGER.debug(message)
                raise RequestError(message)

            except ClientError as err:
                message = f"Error requesting data from {url}: {str(err)}"
                _LOGGER.debug(message)
                raise RequestError(message)

        # To prevent timeouts, ensure that only one gets through at a time.
        # Exception is when this is a login request AND there is already a lock, in that case
        # we're sending the request anyways as we know there is no active request now.
        async with self._lock:

            # If we had something for an authentication task and it is done then get the result and clear it out.
            if self._authentication_task is not None:
                authentication_task = await self.authenticate(wait=False)
                if authentication_task.done():
                    _LOGGER.debug(
                        "Scheduled token refresh completed, ensuring no exception."
                    )
                    self._authentication_task = None
                    try:
                        # Get the result so any exception is raised.
                        authentication_task.result()
                    except asyncio.CancelledError:
                        pass
                    except (RequestError, AuthenticationError) as auth_err:
                        message = f"Scheduled token refresh failed: {str(auth_err)}"
                        _LOGGER.debug(message)

            # Check if token has to be refreshed.
            if (
                self._security_token[2] is None
                or self._security_token[2] <= datetime.utcnow()
            ):
                # Token has to be refreshed, get authentication task if running otherwise start a new one.
                if self._security_token[0] is None:
                    # Wait for authentication task to be completed.
                    _LOGGER.debug(
                        f"Waiting for updated token, last refresh was {self._security_token[3]}"
                    )
                    try:
                        await self.authenticate(wait=True)
                    except AuthenticationError as auth_err:
                        message = f"Error trying to re-authenticate to snoo service: {str(auth_err)}"
                        _LOGGER.debug(message)
                        raise AuthenticationError(message)
                else:
                    # We still have a token, we can continue this request with that token and schedule
                    # task to refresh token unless one is already running
                    await self.authenticate(wait=False)

            if not headers:
                headers = {}

            headers["Authorization"] = self._security_token[0]

            # _LOGGER.debug(f"Sending {method} request to {url}.")
            # Do the request
            try:
                # First try
                try:
                    return await call_method(
                        method=method,
                        url=url,
                        websession=websession,
                        headers=headers,
                        params=params,
                        data=data,
                        json=json,
                        allow_redirects=allow_redirects,
                    )
                except ClientResponseError as err:
                    # Handle only if status is 401, we then re-authenticate and retry the request
                    if err.status == 401:
                        self._security_token = (None, None, None, self._security_token[3])
                        _LOGGER.debug("Status 401 received, re-authenticating.")
                        try:
                            await self.authenticate(wait=True)
                        except AuthenticationError as auth_err:
                            # Raise authentication error, we need a new token to continue and not getting it right
                            # now.
                            message = f"Error trying to re-authenticate to snoo service: {str(auth_err)}"
                            _LOGGER.debug(message)
                            raise AuthenticationError(message)
                    else:
                        # Some other error, re-raise.
                        raise err

                # Re-authentication worked, resend request that had failed.
                return await call_method(
                    method=method,
                    url=url,
                    websession=websession,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json,
                    allow_redirects=allow_redirects,
                )

            except ClientResponseError as err:
                message = (
                    f"Error requesting data from {url}: {err.status} - {err.message}"
                )
                _LOGGER.debug(message)
                if getattr(err, "status") and err.status == 401:
                    # Received unauthorized, reset token and start task to get a new one.
                    self._security_token = (None, None, None, self._security_token[3])
                    await self.authenticate(wait=False)
                    raise AuthenticationError(message)

                raise RequestError(message)

            except ClientError as err:
                message = f"Error requesting data from {url}: {str(err)}"
                _LOGGER.debug(message)
                raise RequestError(message)

    async def _api_authenticate(self) -> Tuple[str, int]:

        async with ClientSession() as session:
            # Perform login to Snoo
            data = {
                "username": self.username,
                "password": self.__credentials.get("password")
            }
            _LOGGER.debug("Performing login to Snoo")
            resp, data = await self.request(
                method="post",
                returns="json",
                url=f"{BASE_ENDPOINT}{LOGIN_URI}",
                websession=session,
                headers = {
                  'Accept': '*/*',
                  'Content-Type': 'application/json',
                  'User-Agent': 'SNOO/2.4.0 (com.happiestbaby.snooapp;) Alamofire/5.3.0',
                },
                data = json.dumps(data),
                login_request=True,
            )

            # Retrieve token
            _LOGGER.debug("Getting token")
            token = f"{data.get('token_type')} {data.get('access_token')}"
            refresh_token = data.get('refresh_token')
            try:
                expires = int(data.get("expires_in", DEFAULT_TOKEN_REFRESH))
            except ValueError:
                _LOGGER.debug(
                    f"Expires {data.get('expires_in')} received is not an integer, using default."
                )
                expires = DEFAULT_TOKEN_REFRESH * 2

        if expires < DEFAULT_TOKEN_REFRESH * 2:
            _LOGGER.debug(
                f"Expires {expires} is less then default {DEFAULT_TOKEN_REFRESH}, setting to default instead."
            )
            expires = DEFAULT_TOKEN_REFRESH * 2

        return token, refresh_token, expires

    async def _authenticate(self) -> None:
        # Retrieve and store the initial security token:
        _LOGGER.debug("Initiating authentication")

        if self._security_token[2] is not None and self._security_token[2] < datetime.utcnow():
            # try to get a new access_token with the stored refresh_token
            token, refresh_token, expires = await self._refresh_token()
            return
        else:
            # Fresh login using the stored credintials
            token, refresh_token, expires = await self._api_authenticate()

        if token is None:
            _LOGGER.debug("No security token received.")
            raise AuthenticationError(
                "Authentication response did not contain a security token yet one is expected."
            )

        _LOGGER.debug(f"Received token that will expire in {expires} seconds")
        self._security_token = (
            token,
            refresh_token,
            datetime.utcnow() + timedelta(seconds=int(expires / 2)),
            datetime.now(),
        )

    async def _refresh_token(self) -> Tuple[str, str, int]:
        # Retrieve and store the initial security token:
        _LOGGER.debug("Refreshing token")

        async with ClientSession() as session:
            # Perform login to Snoo
            data = {
                "refresh_token": self._security_token[1]
            }
            _LOGGER.debug("Performing login to Snoo")
            resp, data = await self.request(
                method="post",
                returns="json",
                url=f"{BASE_ENDPOINT}{REFRESH_URI}",
                websession=session,
                headers = {
                  'Accept': '*/*',
                  'Content-Type': 'application/json',
                  'User-Agent': 'SNOO/2.4.0 (com.happiestbaby.snooapp;) Alamofire/5.3.0',
                },
                data = json.dumps(data),
                login_request=True,
            )

            # Retrieve token
            _LOGGER.debug("Getting token")
            token = f"{data.get('token_type')} {data.get('access_token')}"
            refresh_token = data.get('refresh_token')
            try:
                expires = int(data.get("expires_in", DEFAULT_TOKEN_REFRESH))
            except ValueError:
                _LOGGER.debug(
                    f"Expires {data.get('expires_in')} received is not an integer, using default."
                )
                expires = DEFAULT_TOKEN_REFRESH * 2

        if expires < DEFAULT_TOKEN_REFRESH * 2:
            _LOGGER.debug(
                f"Expires {expires} is less then default {DEFAULT_TOKEN_REFRESH}, setting to default instead."
            )
            expires = DEFAULT_TOKEN_REFRESH * 2

        return token, refresh_token, expires

    async def authenticate(self, wait: bool = True) -> Optional[asyncio.Task]:
        """Authenticate and get a security token."""
        if self.username is None or self.__credentials["password"] is None:
            message = "No username/password, most likely due to previous failed authentication."
            _LOGGER.debug(message)
            raise InvalidCredentialsError(message)

        if self._invalid_credentials:
            message = "Credentials are invalid, update username/password to re-try authentication."
            _LOGGER.debug(message)
            raise InvalidCredentialsError(message)

        if self._authentication_task is None:
            # No authentication task is currently running, start one
            _LOGGER.debug(
                f"Scheduling token refresh, last refresh was {self._security_token[3]}"
            )
            self._authentication_task = asyncio.create_task(
                self._authenticate(), name="Snoo_Authenticate"
            )

        if wait:
            try:
                await self._authentication_task
            except (RequestError, AuthenticationError) as auth_err:
                # Raise authentication error, we need a new token to continue and not getting it right
                # now.
                self._authentication_task = None
                raise AuthenticationError(str(auth_err))
            self._authentication_task = None

        return self._authentication_task

    async def get_account(self) -> Optional[dict]:

        _LOGGER.debug("Retrieving account information")

        # Retrieve the account
        account = None
        _, accounts_resp = await self.request(
            method="get", returns="json", url=f"{BASE_ENDPOINT}{ACCOUNT_URI}"
        )
        if accounts_resp is not None:
            account_id = accounts_resp.get("userId")
            if account_id is not None:
                _LOGGER.debug(
                    f"Got account {account_id} with name {accounts_resp.get('givenName')}"
                )
                account = accounts_resp
        else:
            _LOGGER.debug(f"No accounts found")

        return account

    async def _get_device_details(self) -> None:

        _LOGGER.debug(f"Retrieving devices for account {self.account['givenName']}")

        _, devices_resp = await self.request(
            method="get",
            returns="json",
            url=f"{BASE_ENDPOINT}{DEVICES_URI}",
        )

        device_state_update_timestmp = datetime.utcnow()
        if devices_resp is not None:
            for device_json in devices_resp:
                serial_number = device_json.get("serialNumber")
                if serial_number is None:
                    _LOGGER.debug(
                        f"No serial number for device for baby id {device_json.get('baby')}."
                    )
                    continue

                if serial_number not in self.devices:
                    snoodevice = await self._add_new_device(device_json)
                else:
                    snoodevice = self.devices[serial_number]

                _LOGGER.debug(
                    f"Updating information for device with serial number {serial_number}"
                )

                config_json = await self.get_configs_for_device(snoodevice)
                session_json = await self.get_session_for_account()
                last_update = snoodevice.last_update

                snoodevice.device = device_json
                snoodevice.config = config_json
                snoodevice.session = session_json

                if (
                    snoodevice._device.get("updatedAt") is not None
                    and snoodevice._device.get("updatedAt") != last_update
                ):
                    _LOGGER.debug(
                        f"State for device {snoodevice.name} was updated to {snoodevice.state}"
                    )

                snoodevice.device_state_update = device_state_update_timestmp
        else:
            _LOGGER.debug(f"No devices found for account {self.account['givenName']}")

        return self.devices

    async def _add_new_device(self, device_json):
        serial_number = device_json.get("serialNumber")
        # device_state_update_timestmp = datetime.utcnow()
        _LOGGER.debug(
            f"Adding new Snoo with serial number {serial_number}"
        )
        snoodevice = SnooDevice(
            api=self,
            account=self.account,
            device_json=device_json,
            baby_json=self.baby
        )
        # snoodevice.device_state_update = device_state_update_timestmp
        self.devices[serial_number] = snoodevice

        return self.devices[serial_number]

    async def get_baby_for_account(self) -> None:

        _LOGGER.debug(f"Retrieving baby details for account {self.account['givenName']}")
        baby = None
        _, baby_resp = await self.request(
            method="get",
            returns="json",
            url=f"{BASE_ENDPOINT}{BABY_URI}",
        )

        if baby_resp is not None:
          baby = baby_resp
        else:
            _LOGGER.debug(
                f"No baby found for account {self.account['givenName']}"
            )
        return baby

    async def get_session_for_account(self) -> Dict:
        # Session information is for the account, not specific to a device for some reason.
        # Don't know how this will work with multiple devices in the same account.
        _LOGGER.debug(f"Retrieving last session details for account {self.account['givenName']}")
        session = None
        _, session_resp = await self.request(
            method="get",
            returns="json",
            url=f"{BASE_ENDPOINT}{SESSION_URI}",
        )

        if session_resp is not None:
          session = session_resp
        else:
            _LOGGER.debug(
                f"No session found for account {self.account['givenName']}"
            )
        return session

    async def get_session_stats_daily_for_account(self, startTime: datetime, detailedLevels=False, levels=True) -> Dict:
        _LOGGER.debug(f"Retrieving session details for given day for account {self.account['givenName']}")

        if self.account is None:
            self.account = await self.get_account()
        if self.baby is None:
            self.baby = await self.get_baby_for_account()

        params = {
            "detailedLevels": str(detailedLevels).lower(),
            "levels": str(levels).lower(),
            "startTime": startTime.isoformat()[:-3]+'Z'     # e.g. "2021-02-04T08:00:00.000Z"
        }

        _LOGGER.debug(f"PARAMS {params}")

        session_stats_daily = None
        _, session_stats_daily_resp = await self.request(
            method="get",
            returns="json",
            url=f"{BASE_ENDPOINT}{SESSION_STATS_DAILY_URI}".format(baby_id=self.baby.get("_id")),
            params=params
        )

        if session_stats_daily_resp is not None:
          session_stats_daily = session_stats_daily_resp
        else:
            _LOGGER.debug(
                f"No session stats found for account {self.account['givenName']} with startTime {startTime}"
            )
        return session_stats_daily

    async def get_session_stats_avg_for_account(self, startTime: datetime, days=False, interval="week") -> Dict:
        _LOGGER.debug(f"Retrieving session details for given day for account {self.account['givenName']}")

        if self.account is None:
            self.account = await self.get_account()
        if self.baby is None:
            self.baby = await self.get_baby_for_account()

        params = {
            "days": str(days).lower(),
            "interval": interval,
            "startTime": startTime.isoformat()[:-3]+'Z'     # e.g. "2021-02-04T08:00:00.000Z"
        }

        session_stats_avg = None
        _, session_stats_avg_resp = await self.request(
            method="get",
            returns="json",
            url=f"{BASE_ENDPOINT}{SESSION_STATS_AVG_URI}".format(baby_id=self.baby.get("_id")),
            params=params
        )

        if session_stats_avg_resp is not None:
          session_stats_avg = session_stats_avg_resp
        else:
            _LOGGER.debug(
                f"No session stats found for account {self.account['givenName']} with startTime {startTime}"
            )
        return session_stats_avg

    async def get_configs_for_device(self, device) -> Dict:
        serial_number = device.device_id
        _LOGGER.debug(f"Retrieving configs for device {serial_number}")

        _, configs_resp = await self.request(
            method="get",
            returns="json",
            url=f"{BASE_ENDPOINT}{DEVICE_CONFIGS_URI.format(serial_number=serial_number)}",
        )

        # config_update_timestmp = datetime.utcnow()
        if configs_resp is not None:
            _LOGGER.debug(
                f"Updated config information for device with serial number {serial_number}"
            )
            # device.config_update = config_update_timestmp
        else:
            _LOGGER.error(f"No configs found for device with serial number {serial_number}")

        return configs_resp


    async def update_device_info(self) -> None:
        """Get up-to-date device info."""
        # if back-to-back requests occur within a threshold, respond to only the first
        # Ensure only 1 update task can run at a time.
        async with self._update:
            call_dt = datetime.utcnow()
            if not self.last_state_update:
                self.last_state_update = call_dt - DEFAULT_DEVICE_UPDATE_INTERVAL
            next_available_call_dt = (
                self.last_state_update + DEFAULT_DEVICE_UPDATE_INTERVAL
            )

            # Ensure we're within our minimum update interval AND update request is not for a specific device
            if call_dt < next_available_call_dt:
                _LOGGER.debug(
                    "Ignoring device update request as it is within throttle window"
                )
                # Only update session details
                for device_id, device in self.devices.items():
                    device.session = await self.get_session_for_account()
                return

            _LOGGER.debug("Updating device information")
            if self.account is None:
                self.account = await self.get_account()
            if self.baby is None:
                self.baby = await self.get_baby_for_account()

            await self._get_device_details()
            if self.devices is None:
                _LOGGER.debug(f"No devices found")
                self.devices = {}

            # Update our last update timestamp UNLESS this is for a specific account
            self.last_state_update = datetime.utcnow()


async def login(username: str, password: str, websession: ClientSession = None) -> API:
    """Log in to the API."""

    # Set the user agent in the headers.
    api = API(username=username, password=password, websession=websession)
    _LOGGER.debug("Performing initial authentication into Snoo")
    try:
        await api.authenticate(wait=True)
    except InvalidCredentialsError as err:
        _LOGGER.error(
            f"Username and/or password are invalid. Update username/password."
        )
        raise err
    except AuthenticationError as err:
        _LOGGER.error(f"Authentication failed: {str(err)}")
        raise err

    # Retrieve and store initial set of devices:
    _LOGGER.debug("Retrieving SNOO information")
    await api.update_device_info()
    return api
