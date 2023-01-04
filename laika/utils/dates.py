import datetime as dt
from datetime import datetime

import pytz
from django.utils import timezone

from laika.utils.exceptions import ServiceException

YYYY_MM_DD = '%Y-%m-%d'
YYYY_MM_DD_HH_MM = '%Y_%m_%d_%H_%M'
YYYY_MM_DD_HH_MM_SS = '%Y-%m-%d %H:%M:%S'
YYYY_MM_DD_HH_MM_SS_FF = '%Y-%m-%d %H:%M:%S.%f'
MMMM_DD_YYYY = '%B %d, %Y'
MMMM_DD_YYYY_SHORT = '%b %d, %Y'
MM_DD_YYYY = '%m-%d-%Y'
YYYYMMDD = '%Y%m%d'
ISO_8601_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
ISO_8601_FORMAT_WITH_TZ = '%Y-%m-%dT%H:%M:%S%z'


def dynamo_timestamp_to_datetime(timestamp):
    timestamp_in_seconds = timestamp / 1000
    return datetime.fromtimestamp(timestamp_in_seconds)


def now_date(time_zone, format=YYYY_MM_DD):
    utc_now = pytz.utc.localize(datetime.utcnow())
    try:
        date = utc_now.astimezone(pytz.timezone(time_zone)).strftime(format)
    except pytz.exceptions.UnknownTimeZoneError:
        date = utc_now.astimezone(pytz.timezone('UTC')).strftime(format)
    return date


def format_iso_date(iso_date, date_format):
    return datetime.fromisoformat(str(iso_date)).strftime(date_format)


def str_date_to_date_formatted(str_date, date_format=YYYY_MM_DD):
    return datetime.strptime(str_date, date_format)


def get_future_date(days_to_add):
    today = dt.date.today()
    return today + dt.timedelta(days=days_to_add)


def validate_timeline_dates(start_date, due_date):
    current_date = timezone.now()
    if due_date and start_date and due_date < start_date:
        raise ServiceException('Due date cannot be older than start date')
    if due_date and due_date < current_date:
        raise ServiceException('Due date cannot be older than current date')
