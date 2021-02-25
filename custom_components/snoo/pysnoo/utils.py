from typing import TYPE_CHECKING, Optional, List, Dict, Any
import ciso8601
import re
import pytz
import datetime

DATE_STR_FORMAT = "%Y-%m-%d"
UTC = pytz.utc
DEFAULT_TIME_ZONE: datetime.tzinfo = pytz.utc
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
DATETIME_RE = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})"
    r"[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
    r"(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d{0,6})?)?"
    r"(?P<tzinfo>Z|[+-]\d{2}(?::?\d{2})?)?$"
)

# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
def parse_datetime(dt_str: str) -> Optional[datetime.datetime]:
    """Parse a string and return a datetime.datetime.
    This function supports time zone offsets. When the input contains one,
    the output uses a timezone with a fixed offset from UTC.
    Raises ValueError if the input is well formatted but not a valid datetime.
    Returns None if the input isn't well formatted.
    """
    if dt_str is None or type(dt_str) == datetime.datetime:
        return dt_str
    try:
        return ciso8601.parse_datetime(dt_str)
    except (ValueError, IndexError):
        pass
    match = DATETIME_RE.match(dt_str)
    if not match:
        return None
    kws: Dict[str, Any] = match.groupdict()
    if kws["microsecond"]:
        kws["microsecond"] = kws["microsecond"].ljust(6, "0")
    tzinfo_str = kws.pop("tzinfo")

    tzinfo: Optional[datetime.tzinfo] = None
    if tzinfo_str == "Z":
        tzinfo = UTC
    elif tzinfo_str is not None:
        offset_mins = int(tzinfo_str[-2:]) if len(tzinfo_str) > 3 else 0
        offset_hours = int(tzinfo_str[1:3])
        offset = datetime.timedelta(hours=offset_hours, minutes=offset_mins)
        if tzinfo_str[0] == "-":
            offset = -offset
        tzinfo = datetime.timezone(offset)
    kws = {k: int(v) for k, v in kws.items() if v is not None}
    kws["tzinfo"] = tzinfo
    return datetime.datetime(**kws)
