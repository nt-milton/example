from django.db import connections

from monitor.laikaql import build_raw_query
from monitor.result import Result
from organization.models import Organization


def run(organization: Organization, query: str) -> Result:
    query = build_raw_query(organization, query)
    with connections['query_monitor'].cursor() as cursor:
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        return Result(columns=columns, data=cursor.fetchall())
