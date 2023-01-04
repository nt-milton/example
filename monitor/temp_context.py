# TODO: Remove after DC-15 and DC-11
import re

from django.db import connection

from monitor.result import Result
from organization.models import Organization


def run(organization: Organization, query: str) -> Result:
    params = [organization.id.hex for _ in re.finditer('%s', query)]
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        return Result(columns=columns, data=cursor.fetchall())
