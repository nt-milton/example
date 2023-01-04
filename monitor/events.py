from integration.constants import AZURE_VENDOR, GCP_VENDOR
from monitor.export import get_latest_result
from monitor.laikaql import LO_TO_SQL_MAPPING
from monitor.models import Monitor, OrganizationMonitor
from monitor.runner import build_unfiltered_query, dry_run
from monitor.sqlutils import _get_table_names, extract_vendor


def match_any_dependency(
    candidate_monitors: list[Monitor], dependencies: set[str]
) -> list[Monitor]:
    return [
        monitor
        for monitor in candidate_monitors
        if _monitor_any_dependencies(monitor, dependencies)
    ]


def org_monitor_match_any(
    organization_monitors: list[OrganizationMonitor], dependencies: set[str]
) -> list[OrganizationMonitor]:
    return [
        om
        for om in organization_monitors
        if _monitor_any_dependencies(om.monitor, dependencies)
    ]


def _monitor_any_dependencies(monitor: Monitor, dependencies: set[str]) -> bool:
    monitor_dependencies = [
        _dependency_from_table(table_name)
        for table_name in _get_table_names(monitor.query)
    ]
    return bool(dependencies.intersection(monitor_dependencies))


def _dependency_from_table(table_name: str) -> str:
    cloud_vendor = extract_vendor(table_name)
    if cloud_vendor:
        return f'{cloud_vendor}_dependency'

    return f'{table_name}_dependency'


def integration_events(vendor_name: str, laika_objects: list[str]) -> set[str]:
    lo_dependencies = set()
    if laika_objects:
        lo_dependencies = {
            f'{LO_TO_SQL_MAPPING[lo]}_dependency' for lo in laika_objects
        }
    lo_dependencies.add(find_integration(vendor_name))
    return lo_dependencies


def find_integration(vendor_name: str) -> str:
    if vendor_name == AZURE_VENDOR:
        return 'azure_dependency'

    if vendor_name == GCP_VENDOR:
        return 'gcp_dependency'

    return f'{vendor_name.lower()}_dependency'


LIMIT = 1


def _has_unfiltered_data(organization_monitor: OrganizationMonitor) -> bool:
    monitor_result = get_latest_result(organization_monitor)
    has_data = bool(monitor_result['data'])
    if not has_data:
        organization = organization_monitor.organization
        monitor = organization_monitor.monitor
        unfiltered_query = build_unfiltered_query(monitor.query, LIMIT)
        result = dry_run(
            organization,
            unfiltered_query,
            monitor.validation_query,
            monitor.runner_type,
        )
        has_data = bool(result.data)
    return has_data
