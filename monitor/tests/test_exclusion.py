import json
from datetime import datetime
from shutil import which

import pytest
from django.core.exceptions import ValidationError

from monitor.exclusion import (
    deprecate_monitor_exclusion,
    exclude_result,
    expand_result_with_exclusion,
    revert_exclusion,
    sort_exclusions,
)
from monitor.export import get_latest_result
from monitor.models import (
    Monitor,
    MonitorExclusion,
    MonitorExclusionEvent,
    MonitorExclusionEventType,
    MonitorHealthCondition,
    MonitorInstanceStatus,
    MonitorType,
)
from monitor.mutations import clone_monitor, clone_organization_monitor
from monitor.result import Result
from monitor.runner import run
from monitor.steampipe import get_vendor_from_table_name
from monitor.tests.factory import (
    create_monitor,
    create_monitor_exclusion,
    create_monitor_exclusion_event,
    create_monitor_result,
    create_organization_monitor,
)
from monitor.tests.functional_tests import (
    CLONE_MONITOR,
    TEST_MONITOR_NAME,
    TEST_QUERY,
    populate_monitor_results,
)
from monitor.validators import get_allowed_columns, validate_exclude_field
from user.tests.factory import create_user


@pytest.mark.functional
@pytest.mark.parametrize(
    'table, columns',
    [
        ('teams', ['name', 'description']),
        ('lo_users', ['first_name', 'email']),
    ],
)
def test_get_allowed_columns(table, columns):
    if get_vendor_from_table_name(table) and not which('steampipe'):
        pytest.skip()
    allowed_columns = get_allowed_columns(table)
    assert set(columns).issubset(set(allowed_columns))


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_validate_valid_exclude_field():
    validate_exclude_field('monitor_results.monitor_result_id')


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_validate_invalid_exclude_field():
    with pytest.raises(
        ValidationError, match='monitor_result is not a valid column in monitors'
    ):
        validate_exclude_field('monitors.monitor_result')


def test_exclude_field_wrong_placeholder_format():
    with pytest.raises(ValidationError, match='Invalid exclude field'):
        validate_exclude_field('monitors.a.b')


def test_exclude_field_wrong_table():
    with pytest.raises(ValidationError, match='monitores is not a valid table'):
        validate_exclude_field('monitores.monitor_id')


def test_exclude_field_query_no_exception():
    validate_exclude_field('lo_users.id', 'select * from lo_users')


def test_exclude_field_query_exception():
    with pytest.raises(ValidationError, match='Placeholder tables do not match query'):
        validate_exclude_field('lo_users.id', 'select * from monitors')


GET_MONITOR_EXCLUSION_CRITERIA = '''
        query monitorExclusions ($organizationMonitorId: ID!) {
          monitorExclusions (
            organizationMonitorId: $organizationMonitorId,
          ) {
            monitorExclusions {
              id
              column
              value
              exclusionDate
              isActive
              snapshot
              justification
            }
          }
        }
    '''


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_monitor_exclusion(
    graphql_client,
    graphql_organization,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='testing_key',
        value='testing_value',
        snapshot={},
        justification='testing_justification',
    )
    create_monitor_exclusion(
        organization_monitor=organization_monitor,
        is_active=False,
        key='inactive_key',
        value='inactive_value',
        snapshot={},
        justification='testing_justification',
    )
    response = graphql_client.execute(
        GET_MONITOR_EXCLUSION_CRITERIA,
        variables={'organizationMonitorId': organization_monitor.id},
    )
    result = response['data']['monitorExclusions']['monitorExclusions']
    assert 'errors' not in response
    assert result is not None
    assert len(result) == 1


CREATE_MONITOR_EXCLUSION_CRITERIA = '''
        mutation createMonitorExclusion (
            $organizationMonitorId: ID!
            $monitorExclusion: MonitorExclusionInputType!
        ) {
          createMonitorExclusion (
            organizationMonitorId: $organizationMonitorId,
            monitorExclusion: $monitorExclusion
          ) {
            monitorExclusions {
              id
              column
              value
              exclusionDate
              isActive
              snapshot
              justification
            }
          }
        }
    '''


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_create_monitor_exclusion_repeated(
    graphql_client,
    graphql_organization,
):
    key = 'organization_organization.id'
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
        exclude_field=key,
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    justification = 'testing'
    create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key=key,
        value=0,
        snapshot={},
        justification=justification,
    )
    populate_monitor_results(organization_monitor)
    response = graphql_client.execute(
        CREATE_MONITOR_EXCLUSION_CRITERIA,
        variables={
            'organizationMonitorId': organization_monitor.id,
            'monitorExclusion': {
                'dataIndexes': [0],
                'justification': justification,
            },
        },
    )
    assert 'errors' in response
    assert len(response['errors']) == 1
    assert 'already exists' in response['errors'][0]['message']


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_create_monitor_exclusion(
    graphql_client,
    graphql_organization,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
        exclude_field='organization_organization.id',
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    populate_monitor_results(organization_monitor)
    justification = 'testing'
    response = graphql_client.execute(
        CREATE_MONITOR_EXCLUSION_CRITERIA,
        variables={
            'organizationMonitorId': organization_monitor.id,
            'monitorExclusion': {
                'dataIndexes': [0],
                'justification': justification,
            },
        },
    )
    result = response['data']['createMonitorExclusion']
    monitor_exclusion = result['monitorExclusions'][0]
    assert 'errors' not in response
    assert result is not None
    assert monitor_exclusion['column'] == monitor.exclude_field
    assert monitor_exclusion['value'] == '0'
    assert monitor_exclusion['justification'] == justification
    assert monitor_exclusion['snapshot'] == json.dumps([0, 'test'])
    assert monitor_exclusion['isActive']
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion=monitor_exclusion['id']
        ).count()
        == 1
    )
    assert (
        MonitorExclusionEvent.objects.filter(monitor_exclusion=monitor_exclusion['id'])
        .order_by('-event_date')
        .first()
        .event_type
        == MonitorExclusionEventType.CREATED
    )


UPDATE_MONITOR_EXCLUSION_CRITERIA = '''
        mutation updateMonitorExclusion (
            $organizationMonitorId: ID!
            $monitorExclusionIds: [String]!
            $justification: String!
        ) {
          updateMonitorExclusion (
            organizationMonitorId: $organizationMonitorId,
            monitorExclusionIds: $monitorExclusionIds,
            justification: $justification
          ) {
            monitorExclusions {
              id
              column
              value
              exclusionDate
              isActive
              snapshot
              justification
            }
          }
        }
    '''


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_update_monitor_exclusion(
    graphql_client,
    graphql_organization,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    monitor_exclusion = create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='testing_key',
        value='testing_value',
        snapshot={},
        justification='testing_justification',
    )
    justification = 'new_justification'
    response = graphql_client.execute(
        UPDATE_MONITOR_EXCLUSION_CRITERIA,
        variables={
            'organizationMonitorId': organization_monitor.id,
            'monitorExclusionIds': [monitor_exclusion.id],
            'justification': justification,
        },
    )
    result = response['data']['updateMonitorExclusion']['monitorExclusions']
    event_type = MonitorExclusionEventType.UPDATED_JUSTIFICATION
    assert 'errors' not in response
    assert result is not None
    assert result[0]['justification'] == justification
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion=monitor_exclusion
        ).count()
        == 2
    )
    assert (
        MonitorExclusionEvent.objects.filter(monitor_exclusion=monitor_exclusion)
        .order_by('-event_date')
        .first()
        .event_type
        == event_type
    )


GET_ORGANIZATION_MONITOR_EXCLUDED_RESULTS = '''
    query organizationMonitorExcludedResults($organizationMonitorId: ID!) {
        organizationMonitorExcludedResults(
            organizationMonitorId: $organizationMonitorId
        ) {
            columns
            data
            fixMeLinks
            exclusionIds
        }
    }
    '''


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_organization_monitor_excluded_data_fix_me_links_with_old_data(
    graphql_client,
    graphql_organization,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        exclude_field='organization_organization.id',
        fix_me_link='organization/$organization_organization.name',
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    populate_monitor_results(organization_monitor)
    create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='organization_organization.id',
        value='1',
        snapshot={},
        justification='testing_justification',
    )
    create_monitor_result(
        organization_monitor=organization_monitor,
        status=MonitorInstanceStatus.TRIGGERED,
        result={
            'data': [],
            'columns': ['id', 'name'],
            'excluded_results': {'1': [1, 'testing']},
        },
    )
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR_EXCLUDED_RESULTS,
        variables={'organizationMonitorId': organization_monitor.id},
    )
    result = response['data']['organizationMonitorExcludedResults']
    assert 'Excluded Date' in result['columns']
    assert 'Last Updated' in result['columns']
    assert 'Justification' in result['columns']
    assert len(result['fixMeLinks']) == 0
    assert len(result['exclusionIds']) > 0


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_organization_monitor_excluded_data_fix_me_links_with_fresh_data(
    graphql_client, graphql_organization, temp_context_runner
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='select id from user_user',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        exclude_field='user_user.email',
        fix_me_link='people/$user_user.username',
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    exclusion_value = 'user_0@heylaika.com'
    create_user(graphql_organization, username='test', email=exclusion_value)
    create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='user_user.email',
        value=exclusion_value,
        snapshot=[],
        justification='testing_justification',
    )
    run(organization_monitor)
    monitor_result = get_latest_result(organization_monitor)
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR_EXCLUDED_RESULTS,
        variables={'organizationMonitorId': organization_monitor.id},
    )
    result = response['data']['organizationMonitorExcludedResults']
    assert 'Excluded Date' in result['columns']
    assert 'Last Updated' in result['columns']
    assert 'Justification' in result['columns']
    assert result['fixMeLinks'] == ['people/test']
    assert len(result['exclusionIds']) > 0
    assert len(monitor_result['data']) == len(monitor_result['variables'])
    assert monitor_result['variables'] == [
        {'user_user.email': 'test@heylaika.com', 'user_user.username': ''}
    ]


REVERT_EXCLUSION_MUTATION = '''
        mutation revertMonitorExclusion(
            $organizationMonitorId: ID!
            $monitorExclusionIds: [String]!
        ) {
            revertMonitorExclusion(
                organizationMonitorId: $organizationMonitorId,
                monitorExclusionIds: $monitorExclusionIds
            ) {
                monitorExclusions {
                    id
                    isActive
                }
            }
        }
    '''


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_revert_monitor_exclusion(graphql_client, graphql_organization):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
        exclude_field='id',
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    populate_monitor_results(organization_monitor)
    monitor_exclusion = create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='id',
        value='1',
        snapshot={},
        justification='testing_justification',
    )
    response = graphql_client.execute(
        REVERT_EXCLUSION_MUTATION,
        variables={
            'organizationMonitorId': organization_monitor.id,
            'monitorExclusionIds': [monitor_exclusion.id],
        },
    )
    result = response['data']['revertMonitorExclusion']['monitorExclusions'][0]
    assert 'errors' not in response
    assert result is not None
    assert result['isActive'] is False
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion=monitor_exclusion
        ).count()
        == 2
    )
    assert (
        MonitorExclusionEvent.objects.filter(monitor_exclusion=monitor_exclusion)
        .order_by('-event_date')
        .first()
        .event_type
        == MonitorExclusionEventType.DELETED
    )


@pytest.mark.functional
def test_can_exclude_without_variables():
    result = create_monitor_result(result={'columns': ['id'], 'data': [['1']]})
    result.organization_monitor.monitor.exclude_field = 'people.people_id'
    result.health_condition = 'empty_results'
    assert not result.can_exclude()


@pytest.mark.functional
def test_can_exclude():
    exclude_field = 'people.people_id'
    result = create_monitor_result(
        result={'columns': ['id'], 'data': [['1']], 'variables': [{exclude_field: '1'}]}
    )
    result.organization_monitor.monitor.exclude_field = exclude_field
    result.health_condition = 'empty_results'
    assert result.can_exclude()


@pytest.mark.functional
def test_can_exclude_empty_result():
    result = create_monitor_result(result={'columns': ['id'], 'data': []})
    result.organization_monitor.monitor.exclude_field = 'people.people_id'
    result.health_condition = 'empty_results'
    assert result.can_exclude()


@pytest.mark.functional
def test_can_exclude_evidence_monitor():
    exclude_field = 'people.people_id'
    result = create_monitor_result(
        result={'columns': ['id'], 'data': [['1']], 'variables': [{exclude_field: '1'}]}
    )
    result.organization_monitor.monitor.exclude_field = exclude_field
    result.health_condition = 'return_results'
    assert not result.can_exclude()


@pytest.mark.functional
def test_add_exclusion_detail(graphql_organization):
    exc_id = 1
    excluded_results = {str(exc_id): {'value': ['123']}}
    user = create_user(
        graphql_organization,
        username='test',
        email='user_0@heylaika.com',
        first_name='Test',
        last_name='user',
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    exclusion = create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='user_user.email',
        snapshot=[],
        justification='testing_justification',
    )
    create_monitor_exclusion_event(exclusion, user)
    exclusion.exclusion_date = datetime.fromisoformat('2021-10-21')
    exclusions = [exclusion]
    last_events = {exc_id: datetime.fromisoformat('2021-10-22')}
    new_data = expand_result_with_exclusion(excluded_results, exclusions, last_events)
    assert list(new_data) == [
        [
            'Test user ()',
            '2021-10-21 00:00:00',
            '2021-10-22 00:00:00',
            'testing_justification',
            '123',
        ]
    ]


@pytest.mark.functional
def test_add_exclusion_detail_deprecated(graphql_organization):
    exc_id = 1
    excluded_results = {str(exc_id): {'value': ['123']}}
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    exclusion = create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='user_user.email',
        snapshot=[],
        justification='testing_justification',
    )
    exclusion.exclusion_date = datetime.fromisoformat('2021-10-21')
    exclusion.save()
    deprecate_monitor_exclusion(exclusion)
    exclusions = [exclusion]
    last_events = {exc_id: datetime.fromisoformat('2021-10-22')}
    new_data = expand_result_with_exclusion(excluded_results, exclusions, last_events)

    assert list(new_data) == [
        [
            '',
            '2021-10-21 00:00:00',
            '2021-10-22 00:00:00',
            'testing_justification',
            '123',
        ]
    ]


def test_missing_exclusion_id():
    exc_id = '1'
    excluded_results = {exc_id: {'value': ['123']}}
    exclusions = []
    last_events = {}
    new_data = expand_result_with_exclusion(excluded_results, exclusions, last_events)
    assert list(new_data) == []


def test_missing_result():
    exc_id = 1
    excluded_results = {}
    exclusions = [
        MonitorExclusion(
            id=exc_id,
            exclusion_date=datetime.fromisoformat('2021-10-21'),
            justification='reason',
        )
    ]
    last_events = {exc_id: datetime.fromisoformat('2021-10-22')}
    new_data = expand_result_with_exclusion(excluded_results, exclusions, last_events)
    assert list(new_data) == []


@pytest.mark.functional
def test_deleted_record_exclusion(
    graphql_client, graphql_organization, temp_context_runner
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='select id from user_user',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        exclude_field='user_user.email',
        fix_me_link='people/$user_user.username',
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    exclusion_value = 'user_0@heylaika.com'
    create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='user_user.email',
        value=exclusion_value,
        snapshot=[],
        justification='testing_justification',
    )
    run(organization_monitor)
    monitor_result = get_latest_result(organization_monitor)
    assert 'data' in monitor_result
    assert 'variables' in monitor_result
    assert len(monitor_result['data']) == len(monitor_result['variables'])
    assert monitor_result['variables'] == [
        {'user_user.email': 'test@heylaika.com', 'user_user.username': ''}
    ]
    assert MonitorExclusion.objects.filter(is_active=True).count() == 1
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__organization_monitor=organization_monitor,
        ).count()
        == 2
    )
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__organization_monitor=organization_monitor,
        )
        .order_by('-event_date')[0]
        .event_type
        == MonitorExclusionEventType.DEPRECATED
    )


@pytest.mark.functional
def test_renewed_record_exclusion(
    graphql_client, graphql_organization, temp_context_runner
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='select id from user_user',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        exclude_field='user_user.email',
        fix_me_link='people/$user_user.username',
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    exclusion_value = 'user_0@heylaika.com'
    create_user(graphql_organization, username='test', email=exclusion_value)
    monitor_exclusion = create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='user_user.email',
        value=exclusion_value,
        snapshot=[],
        justification='testing_justification',
    )
    deprecate_monitor_exclusion(monitor_exclusion)
    run(organization_monitor)
    monitor_result = get_latest_result(organization_monitor)
    assert 'data' in monitor_result
    assert 'variables' in monitor_result
    assert len(monitor_result['data']) == len(monitor_result['variables'])
    assert monitor_result['variables'] == [
        {'user_user.email': 'test@heylaika.com', 'user_user.username': ''}
    ]
    assert MonitorExclusion.objects.filter(is_active=True).count() == 1
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__organization_monitor=organization_monitor,
        ).count()
        == 3
    )
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__organization_monitor=organization_monitor,
        )
        .order_by('-event_date')[0]
        .event_type
        == MonitorExclusionEventType.RENEWED
    )


@pytest.mark.functional
def test_invalid_exclusion_renewal(
    graphql_client, graphql_organization, temp_context_runner
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='select id from user_user',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        exclude_field='user_user.email',
        fix_me_link='people/$user_user.username',
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    exclusion_value = 'user_0@heylaika.com'
    create_user(graphql_organization, username='test', email=exclusion_value)
    create_monitor_exclusion(
        organization_monitor=organization_monitor,
        key='user_user.email',
        value=exclusion_value,
        snapshot=[],
        justification='testing_justification',
    )
    run(organization_monitor)
    monitor_result = get_latest_result(organization_monitor)
    assert 'data' in monitor_result
    assert 'variables' in monitor_result
    assert len(monitor_result['data']) == len(monitor_result['variables'])
    assert monitor_result['variables'] == [
        {'user_user.email': 'test@heylaika.com', 'user_user.username': ''}
    ]
    assert MonitorExclusion.objects.filter(is_active=True).count() == 1
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__organization_monitor=organization_monitor,
        ).count()
        == 1
    )
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__organization_monitor=organization_monitor,
        )
        .order_by('-event_date')[0]
        .event_type
        != MonitorExclusionEventType.RENEWED
    )


def test_sort():
    exclusion_list = [
        MonitorExclusion(
            exclusion_date=datetime.fromisoformat('2021-10-21'), value='a'
        ),
        MonitorExclusion(
            exclusion_date=datetime.fromisoformat('2021-10-21'), value='b'
        ),
        MonitorExclusion(
            exclusion_date=datetime.fromisoformat('2021-10-22'), value='c'
        ),
    ]
    sorted_list = sort_exclusions(exclusion_list)
    assert [x.value for x in sorted_list] == ['c', 'a', 'b']


def test_sort_int():
    exclusion_list = [
        MonitorExclusion(
            exclusion_date=datetime.fromisoformat('2021-10-21'), value='2'
        ),
        MonitorExclusion(
            exclusion_date=datetime.fromisoformat('2021-10-21'), value='11'
        ),
        MonitorExclusion(
            exclusion_date=datetime.fromisoformat('2021-10-22'), value='5'
        ),
    ]
    sorted_list = sort_exclusions(exclusion_list)
    assert [x.value for x in sorted_list] == ['5', '2', '11']


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_system_monitor_update(graphql_client, graphql_organization):
    name = 'original name'
    description = 'original description'
    query = 'select id from user_user'
    monitor = create_monitor(
        name=name,
        description=description,
        query=query,
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization, monitor=monitor
    )
    new_name = 'new name'
    new_description = 'new description'
    new_query = 'select id, first_name, last_name from user_user'
    response = graphql_client.execute(
        CLONE_MONITOR,
        variables={
            'id': monitor.id,
            'name': new_name,
            'description': new_description,
            'query': new_query,
        },
    )
    graphql_monitor = response['data']['updateMonitor']['organizationMonitor'][
        'monitor'
    ]
    monitor.refresh_from_db()
    organization_monitor.refresh_from_db()
    assert monitor.name == name
    assert monitor.description == description
    assert monitor.query == query
    assert organization_monitor.name == new_name
    assert organization_monitor.description == new_description
    assert organization_monitor.query == new_query
    assert graphql_monitor['monitorType'] == MonitorType.SYSTEM
    assert graphql_monitor['id'] == str(monitor.id)
    assert graphql_monitor['name'] == new_name
    assert graphql_monitor['description'] == new_description
    assert graphql_monitor['query'] == new_query


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_custom_monitor_update(graphql_client, graphql_organization):
    name = 'original name'
    description = 'original description'
    query = 'select id from user_user'
    monitor = create_monitor(
        name=name,
        description=description,
        query=query,
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization, monitor=monitor
    )
    new_monitor = clone_monitor(graphql_organization, monitor)
    new_organization_monitor = clone_organization_monitor(
        organization_monitor, new_monitor
    )
    new_name = 'new name'
    new_description = 'new description'
    new_query = 'select from user_user'
    response = graphql_client.execute(
        CLONE_MONITOR,
        variables={
            'id': new_monitor.id,
            'name': new_name,
            'description': new_description,
            'query': new_query,
        },
    )
    graphql_monitor = response['data']['updateMonitor']['organizationMonitor'][
        'monitor'
    ]
    monitor.refresh_from_db()
    organization_monitor.refresh_from_db()
    assert monitor.name == name
    assert monitor.description == description
    assert monitor.query == query
    assert new_organization_monitor.name == new_name
    assert new_organization_monitor.description == new_description
    assert new_organization_monitor.query == new_query
    assert graphql_monitor['monitorType'] == MonitorType.CUSTOM
    assert graphql_monitor['id'] == str(new_monitor.id)
    assert graphql_monitor['name'] == new_name
    assert graphql_monitor['description'] == new_description
    assert graphql_monitor['query'] == new_query


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_system_monitor_to_custom_monitor_transition(
    graphql_client, graphql_organization
):
    name = 'original name'
    description = 'original description'
    query = 'select id from user_user'
    monitor = create_monitor(
        name=name,
        description=description,
        query=query,
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization, monitor=monitor
    )
    new_name = 'new name'
    new_description = 'new description'
    new_query = 'select id last_name from organization_organization'
    response = graphql_client.execute(
        CLONE_MONITOR,
        variables={
            'id': monitor.id,
            'name': new_name,
            'description': new_description,
            'query': new_query,
        },
    )
    graphql_org_monitor = response['data']['updateMonitor']['organizationMonitor']
    graphql_monitor = graphql_org_monitor['monitor']
    monitor.refresh_from_db()
    organization_monitor.refresh_from_db()
    new_monitor = Monitor.objects.get(id=graphql_monitor['id'])
    assert monitor.id != new_monitor.id
    assert monitor.name == name
    assert monitor.description == description
    assert monitor.query == query
    assert new_monitor.name == name
    assert new_monitor.description == description
    assert new_monitor.query == query
    assert organization_monitor.name == new_name
    assert organization_monitor.description == new_description
    assert organization_monitor.query == new_query
    assert graphql_monitor['monitorType'] == MonitorType.CUSTOM
    assert graphql_monitor['id'] == str(new_monitor.id)
    assert graphql_monitor['name'] == new_name
    assert graphql_monitor['description'] == new_description
    assert graphql_monitor['query'] == new_query


@pytest.fixture
def original_result():
    return {
        'data': [['AZURE-0f63f0b9-b0f1-48fc-b2be-eabaae6b8bd0', 'Taj', 'Sangha']],
        'columns': ['id', 'first_name', 'last_name'],
        'variables': [{'lo_users.id': 'AZURE-0f63f0b9-b0f1-48fc-b2be-eabaae6b8bd0'}],
        'excluded_results': {
            '64': {
                'value': ['owner.dev@heylaika.com', '', ''],
                'variables': {'lo_users.id': 'owner.dev@heylaika.com'},
            }
        },
    }


@pytest.fixture
def exclusion():
    return MonitorExclusion(
        id='65', value='AZURE-0f63f0b9-b0f1-48fc-b2be-eabaae6b8bd0', key='lo_users.id'
    )


def test_exclusion(original_result, exclusion):
    original = Result(**original_result)
    excluded = exclude_result(original, [exclusion])
    assert len(excluded.excluded_results) == len(original.data) + 1
    assert len(excluded.data) == len(original.data) - 1


def test_revert_exclusion(original_result):
    original = Result(**original_result)
    reverted = revert_exclusion(original, 64)
    assert len(reverted.excluded_results) == len(original.excluded_results) - 1
    assert len(reverted.data) == len(original.data) + 1
    assert len(reverted.variables) == len(original.variables) + 1


def test_revert_missing_exclusion(original_result):
    original = Result(**original_result)
    reverted = revert_exclusion(original, 100)
    assert reverted.excluded_results == original.excluded_results
    assert reverted.data == original.data
    assert reverted.variables == original.variables


def test_exclusion_and_revert(original_result, exclusion):
    original = Result(**original_result)
    excluded = exclude_result(original, [exclusion])
    reverted = revert_exclusion(excluded, exclusion.id)
    assert reverted.excluded_results == original.excluded_results
    assert reverted.data == original.data
    assert reverted.variables == original.variables
