from blueprint.constants import STATUS_NOT_PRESCRIBED, STATUS_PRESCRIBED


def get_status_filters() -> dict:
    return dict(
        id='status',
        category='Status',
        items=[
            dict(
                id=STATUS_PRESCRIBED,
                name='Prescribed',
            ),
            dict(
                id=STATUS_NOT_PRESCRIBED,
                name='Not Prescribed',
            ),
        ],
    )
