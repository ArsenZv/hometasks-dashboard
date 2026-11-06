"""Single source of "now" for the dashboard: naive datetime in Paris time.

Stored timestamps are naive local (Paris) times, so everything that needs the
current time must use now() instead of datetime.now() (which follows the
container's TZ, UTC by default).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Europe/Paris')


def now():
    return datetime.now(TIMEZONE).replace(tzinfo=None)
