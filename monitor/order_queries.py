from django.db.models import Case, F, Value, When
from django.db.models.fields import IntegerField

from .models import MonitorInstanceStatus

status_order_ascend = [
    MonitorInstanceStatus.NO_DATA_DETECTED,
    MonitorInstanceStatus.HEALTHY,
    MonitorInstanceStatus.CONNECTION_ERROR,
    MonitorInstanceStatus.TRIGGERED,
]


def get_status_order(order: str) -> Case:
    list_order = status_order_ascend.copy()
    if order == 'descend':
        list_order.reverse()
    return Case(
        *[
            When(status=status, then=Value(pos))
            for pos, status in enumerate(list_order)
        ],
        default=list_order.index(MonitorInstanceStatus.NO_DATA_DETECTED),
        output_field=IntegerField()
    )


def build_order_queries(order_by: list) -> list:
    order_queries = []
    for order_declaration in order_by:
        field = order_declaration.get('field')
        order = order_declaration.get('order')
        if field == 'status':
            status_order = get_status_order(order)
            order_queries.append(status_order)
        else:
            expression = (
                F(field).desc(nulls_last=True)
                if order == 'descend'
                else F(field).asc(nulls_last=True)
            )
            order_queries.append(expression)
    return order_queries


def build_list_of_order_queries(order_by: list) -> list:
    return [*build_order_queries(order_by), F('last_run').desc(nulls_last=True)]
