import pytest

from monitor.data_loaders import MonitorSubtaskLoader, group_by_subtask_reference
from monitor.models import Monitor, OrganizationMonitor
from monitor.tests.factory import create_monitor, create_organization_monitor
from organization.tests import create_organization
from program.constants import SUBTASK_MONITOR_STATUS_EMPTY as MONITOR_EMPTY
from program.constants import SUBTASK_MONITOR_STATUS_NO_RELATED as NO_RELATED
from program.constants import SUBTASK_MONITOR_STATUS_RELATED as MONITOR_RELATED
from user.tests import create_user


def test_group_by_subtask_reference_keys():
    org_monitors = [
        OrganizationMonitor(id=1, monitor=Monitor(subtask_reference='123')),
        OrganizationMonitor(id=2, monitor=Monitor(subtask_reference='456')),
    ]
    subtask_references = group_by_subtask_reference(org_monitors)
    assert '123' in subtask_references
    assert '456' in subtask_references


def test_group_by_subtask_reference_collections():
    org_monitors = [
        OrganizationMonitor(id=1, monitor=Monitor(subtask_reference='id1\nid2')),
        OrganizationMonitor(id=2, monitor=Monitor(subtask_reference='id1')),
    ]

    subtask_references = group_by_subtask_reference(org_monitors)
    assert len(subtask_references['id1']) == 2
    assert len(subtask_references['id2']) == 1


@pytest.mark.functional
@pytest.mark.parametrize(
    'subtask_status, create_new_monitor,create_new_organization_monitor, expected',
    [
        (MONITOR_EMPTY, False, False, 0),
        (NO_RELATED, True, False, 0),
        (MONITOR_RELATED, True, True, 1),
    ],
)
def test_subtask_dataloader(
    subtask_status, create_new_monitor, create_new_organization_monitor, expected
):
    uuid = '100baaf7-43d4-4bad-b41b-ee74d4d74156'
    organization = create_organization()

    if create_new_monitor:
        new_monitor = create_monitor(
            name='no related monitor', query='', subtask_reference=uuid
        )

    if create_new_organization_monitor:
        create_organization_monitor(organization, new_monitor)

    context = Context()
    context.user = create_user(organization=organization)
    loader = MonitorSubtaskLoader.with_context(context)
    status, org_monitors = loader.batch_load_fn([uuid]).get()[0]
    assert status == subtask_status
    assert len(org_monitors) == expected


class Context:
    pass
