from django.db.models import F


def get_default_order_by_query(default_field, **kwargs):
    order_by = kwargs.get('order_by', {'field': default_field, 'order': 'ascend'})
    field = order_by.get('field')
    order = order_by.get('order')
    order_query = get_order_query(field, order)

    return order_query


def get_order_query(field, order):
    order_query = (
        F(field).desc(nulls_last=True)
        if order == 'descend'
        else F(field).asc(nulls_last=True)
    )
    return order_query


def get_order_queries(order_inputs):
    order_queries = []
    for order_input in order_inputs:
        field = order_input.get('field')
        order = order_input.get('order')
        order_query = (
            F(field).desc(nulls_last=True)
            if order == 'descend'
            else F(field).asc(nulls_last=True)
        )
        order_queries.append(order_query)
    return order_queries
