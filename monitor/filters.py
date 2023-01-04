from django.db.models import Q

from integration.factory import get_integration_name
from monitor.constants import (
    INTEGRATION_DESCRIPTION,
    INTEGRATION_SOURCES,
    LAIKA_SOURCES,
    SOURCE_SYSTEM_CHOICES,
)
from monitor.models import Monitor, MonitorInstanceStatus, MonitorStatus, MonitorType
from monitor.types import CUSTOM, LAIKA_APP
from organization.models import Organization


def get_monitor_filters(organization: Organization) -> list:
    return [
        get_status_filters(),
        get_active_filters(),
        get_sources_filters(organization),
    ]


def get_monitor_query(organization_id: str, filters: dict, search: str) -> Q:
    query = filter_by_organization(organization_id)
    query &= filter_by_search(search)
    query &= filter_by_status(filters)
    query &= filter_by_control(filters)
    query &= filter_by_active(filters)
    query &= filter_by_sources(filters)
    return query


def get_status_filters() -> dict:
    return dict(
        id='status',
        category='Status',
        items=[
            dict(
                id=MonitorInstanceStatus.HEALTHY,
                name='Healthy',
            ),
            dict(
                id=MonitorInstanceStatus.TRIGGERED,
                name='Flagged',
            ),
            dict(
                id=MonitorInstanceStatus.CONNECTION_ERROR,
                name='Connection Error',
            ),
            dict(
                id=MonitorInstanceStatus.NO_DATA_DETECTED,
                name='No Data Detected',
            ),
        ],
    )


def filter_by_status(filters: dict) -> Q:
    query = Q()
    status = filters.get('status', [])
    if status:
        query &= Q(status__in=status)
    return query


def get_active_filters() -> dict:
    return dict(
        id='active',
        category='Active',
        items=[
            dict(
                id=MonitorStatus.ACTIVE,
                name='Active',
            ),
            dict(
                id=MonitorStatus.INACTIVE,
                name='Inactive',
            ),
        ],
    )


def filter_by_active(filters: dict) -> Q:
    query = Q()
    active = filters.get('active', [])
    if active:
        active = map(lambda status: status == MonitorStatus.ACTIVE, active)
        query &= Q(active__in=active)
    return query


def get_sources_filters(organization: Organization) -> dict:
    monitors = Monitor.objects.filter(organization_monitors__organization=organization)
    sources_systems: list[str] = []
    sources: list[dict] = []
    for monitor in monitors:
        if monitor.source_systems:
            sources_systems += monitor.source_systems
        if monitor.monitor_type == MonitorType.CUSTOM and len(sources) == 0:
            sources.append(dict(id=MonitorType.CUSTOM, name=CUSTOM))

    can_add_laika_sources = True

    for alias, name in SOURCE_SYSTEM_CHOICES:
        if alias in sources_systems and INTEGRATION_DESCRIPTION in name:
            sources.append(
                dict(
                    id=alias,
                    name=get_integration_name(alias),
                )
            )
        elif (
            alias in sources_systems
            and INTEGRATION_DESCRIPTION not in name
            and can_add_laika_sources
        ):
            can_add_laika_sources = False
            sources.append(
                dict(
                    id=LAIKA_APP,
                    name=LAIKA_APP,
                )
            )

    return dict(id='sources', category='Source(s)', items=[*sources])


def get_query_for_source(sources: list) -> Q:
    query = Q()
    for source, _ in sources:
        query |= Q(monitor__source_systems__contains=source)
    return query


def get_query_for_laika_monitors() -> Q:
    return get_query_for_source(LAIKA_SOURCES)


def get_query_for_non_laika_monitors() -> Q:
    return get_query_for_source(INTEGRATION_SOURCES)


def filter_by_sources(filters: dict) -> Q:
    query = Q()
    sources = filters.get('sources', [])
    for source in sources:
        if LAIKA_APP == source:
            query |= get_query_for_laika_monitors()
        elif MonitorType.CUSTOM == source:
            query &= Q(monitor__monitor_type=MonitorType.CUSTOM)
        else:
            query &= Q(monitor__source_systems__contains=sources)
    return query


def filter_by_organization(organization_id: str) -> Q:
    return Q(organization_id=organization_id)


def filter_by_control(filters: dict) -> Q:
    query = Q()
    control_id = filters.get('controlId')
    if control_id:
        query &= Q(controls__id=control_id)
    return query


def filter_by_search(search: str) -> Q:
    query = Q()
    if search:
        query &= Q(monitor__name__icontains=search)
    return query
