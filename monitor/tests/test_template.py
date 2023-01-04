import pytest

from monitor.models import (
    MonitorHealthCondition,
    MonitorInstanceStatus,
    MonitorResult,
    MonitorType,
)
from monitor.runner import run
from monitor.sqlutils import get_raw_selected_columns
from monitor.template import TEMPLATE_PREFIX, build_fix_links, build_query_for_variables
from monitor.tests.factory import (
    create_monitor,
    create_monitor_result,
    create_organization_monitor,
)
from monitor.tests.functional_tests import GET_ORGANIZATION_MONITOR
from organization.tests import create_organization
from user.tests.factory import create_user

TEST_MONITOR_NAME = 'Test Monitor 1'
TRIGGERED = MonitorInstanceStatus.TRIGGERED


@pytest.mark.functional
def test_hardcoded_links():
    result = create_monitor_result(status=TRIGGERED, result={'data': ['record_1']})
    hardcoded_link = '/hardcoded_link'
    result.organization_monitor.monitor.fix_me_link = hardcoded_link
    links = build_fix_links(result.organization_monitor, result.result)

    assert links == [hardcoded_link]


@pytest.mark.functional
def test_case_sensitive_link():
    result = create_monitor_result(status=TRIGGERED, result={'data': ['record_1']})
    hardcoded_link = '/people/userId=1'
    result.organization_monitor.monitor.fix_me_link = hardcoded_link
    links = build_fix_links(result.organization_monitor, result.result)

    assert links == [hardcoded_link]


@pytest.mark.functional
def test_case_insensitive_placeholders():
    username = 'df3f21d7-0d11-4690-bb61-829119c1cf36'
    result = create_monitor_result(
        status=TRIGGERED,
        result={'data': ['record_1'], 'variables': [{'people.username': username}]},
    )
    fix_me_link = '/people/userId=$PeoPle.usErName'
    result.organization_monitor.monitor.fix_me_link = fix_me_link
    links = build_fix_links(result.organization_monitor, result.result)

    assert links == [f'/people/userId={username}']


@pytest.fixture
def load_fix_me_links_data():
    for i in range(1, 5):
        organization = create_organization(
            name=f'Organization {i}',
            description=f'Description {i}',
            website=f'Website {i}',
            number_of_employees=i,
        )
        create_user(
            organization,
            email=f'{i}@heylaika.com',
            first_name=f'User {i}',
            last_name=i,
        )


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_fix_me_links_and_exclusion_for_system_monitor(
    graphql_client,
    graphql_organization,
    temp_context_runner,  # noqa
    load_fix_me_links_data,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='select * from organization_organization',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        fix_me_link='/monitors/$organization_organization.id',
        exclude_field='organization_organization.name',
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    run(organization_monitor)
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor.id}
    )
    last_result = response['data']['organizationMonitor']['lastResult']
    fix_me_links = last_result['fixMeLinks']
    can_exclude = last_result['canExclude']
    assert 'errors' not in response
    assert len(fix_me_links) != 0
    assert can_exclude


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_fix_me_links_and_exclusion_for_custom_monitor(
    graphql_client,
    graphql_organization,
    temp_context_runner,  # noqa
    load_fix_me_links_data,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='select * from organization_organization',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        monitor_type=MonitorType.CUSTOM,
        fix_me_link='/monitors/$organization_organization.id',
        exclude_field='organization_organization.name',
        organization=graphql_organization,
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    run(organization_monitor)
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor.id}
    )
    last_result = response['data']['organizationMonitor']['lastResult']
    fix_me_links = last_result['fixMeLinks']
    can_exclude = last_result['canExclude']
    assert 'errors' not in response
    assert fix_me_links == []
    assert not can_exclude


@pytest.mark.functional(permissions=['monitor.view_monitor'])
@pytest.mark.parametrize(
    'query, parameters, health_condition, expected',
    [
        (
            'select * from organization_organization',
            '',
            MonitorHealthCondition.RETURN_RESULTS,
            [],
        ),
        (
            'select * from organization_organization',
            '/monitors/$organization_organization.name',
            MonitorHealthCondition.RETURN_RESULTS,
            [
                '/monitors/Organization 1',
                '/monitors/Organization 2',
                '/monitors/Organization 3',
                '/monitors/Organization 4',
            ],
        ),
        (
            'select * from organization_organization',
            '/monitors/$organization_organization.name'
            '/$organization_organization.description',
            MonitorHealthCondition.RETURN_RESULTS,
            [
                '/monitors/Organization 1/Description 1',
                '/monitors/Organization 2/Description 2',
                '/monitors/Organization 3/Description 3',
                '/monitors/Organization 4/Description 4',
            ],
        ),
        (
            'select name from organization_organization',
            '/monitors/$organization_organization.name',
            MonitorHealthCondition.RETURN_RESULTS,
            [
                '/monitors/Organization 1',
                '/monitors/Organization 2',
                '/monitors/Organization 3',
                '/monitors/Organization 4',
            ],
        ),
        (
            'select name, description from organization_organization',
            '/monitors/$organization_organization.name'
            '/$organization_organization.description',
            MonitorHealthCondition.RETURN_RESULTS,
            [
                '/monitors/Organization 1/Description 1',
                '/monitors/Organization 2/Description 2',
                '/monitors/Organization 3/Description 3',
                '/monitors/Organization 4/Description 4',
            ],
        ),
        (
            'select name from organization_organization',
            '/monitors/$organization_organization.description',
            MonitorHealthCondition.RETURN_RESULTS,
            [
                '/monitors/Description 1',
                '/monitors/Description 2',
                '/monitors/Description 3',
                '/monitors/Description 4',
            ],
        ),
        ('select * from invalid_table', '', MonitorHealthCondition.EMPTY_RESULTS, []),
        (
            'select invalid_column from invalid_table',
            '',
            MonitorHealthCondition.EMPTY_RESULTS,
            [],
        ),
        (
            'select invalid_column from organization_organization',
            '',
            MonitorHealthCondition.EMPTY_RESULTS,
            [],
        ),
        (
            'select * from organization_organization',
            '/monitors/$organization_organization.number_of_employees',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/1',
                '/monitors/2',
                '/monitors/3',
                '/monitors/4',
            ],
        ),
        (
            'select * from organization_organization',
            '/monitors/$organization_organization.name',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1',
                '/monitors/Organization 2',
                '/monitors/Organization 3',
                '/monitors/Organization 4',
            ],
        ),
        (
            'select name from organization_organization',
            '/monitors/$organization_organization.name',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1',
                '/monitors/Organization 2',
                '/monitors/Organization 3',
                '/monitors/Organization 4',
            ],
        ),
        (
            'select * from organization_organization',
            '/monitors/$organization_organization.name'
            '/$organization_organization.description',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1/Description 1',
                '/monitors/Organization 2/Description 2',
                '/monitors/Organization 3/Description 3',
                '/monitors/Organization 4/Description 4',
            ],
        ),
        (
            'select id from organization_organization',
            '/monitors/$organization_organization.name'
            '/$organization_organization.description',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1/Description 1',
                '/monitors/Organization 2/Description 2',
                '/monitors/Organization 3/Description 3',
                '/monitors/Organization 4/Description 4',
            ],
        ),
        (
            'select name, description from organization_organization',
            '/monitors/$organization_organization.name'
            '/$organization_organization.description',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1/Description 1',
                '/monitors/Organization 2/Description 2',
                '/monitors/Organization 3/Description 3',
                '/monitors/Organization 4/Description 4',
            ],
        ),
        (
            'select description from organization_organization',
            '/monitors/$organization_organization.name',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1',
                '/monitors/Organization 2',
                '/monitors/Organization 3',
                '/monitors/Organization 4',
            ],
        ),
        (
            'select * from organization_organization as o '
            'left join user_user as u on u.organization_id = o.id',
            '/monitors/$organization_organization.name/$user_user.email',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1/1@heylaika.com',
                '/monitors/Organization 2/2@heylaika.com',
                '/monitors/Organization 3/3@heylaika.com',
                '/monitors/Organization 4/4@heylaika.com',
            ],
        ),
        (
            'select o.name, u.email from organization_organization as o '
            'left join user_user as u on u.organization_id = o.id',
            '/monitors/$organization_organization.name/$user_user.email',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Organization 1/1@heylaika.com',
                '/monitors/Organization 2/2@heylaika.com',
                '/monitors/Organization 3/3@heylaika.com',
                '/monitors/Organization 4/4@heylaika.com',
            ],
        ),
        (
            'select o.name, u.email from organization_organization as o '
            'left join user_user as u on u.organization_id = o.id',
            '/monitors/$organization_organization.description'
            '/$user_user.first_name/$user_user.last_name',
            MonitorHealthCondition.EMPTY_RESULTS,
            [
                '/monitors/Description 1/User 1/1',
                '/monitors/Description 2/User 2/2',
                '/monitors/Description 3/User 3/3',
                '/monitors/Description 4/User 4/4',
            ],
        ),
    ],
)
def test_fix_me_links_for_monitor_results(
    graphql_client,
    graphql_organization,
    temp_context_runner,  # noqa
    load_fix_me_links_data,
    query,
    parameters,
    health_condition,
    expected,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=f"{query} where name != ''",
        health_condition=health_condition,
        fix_me_link=parameters,
        exclude_field='ignore.me',
    )
    organization_monitor = create_organization_monitor(
        graphql_organization, monitor, status=MonitorInstanceStatus.NO_DATA_DETECTED
    )
    run(organization_monitor)
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor.id}
    )
    last_result = response['data']['organizationMonitor']['lastResult']
    fix_me_links = last_result['fixMeLinks']
    assert 'errors' not in response
    assert fix_me_links == expected
    assert monitor.fix_me_link not in fix_me_links


@pytest.mark.functional
def test_monitor_exclusion_variables_present_after_run(
    temp_context_runner,  # noqa
):
    exclusion_key = 'organization_organization.name'
    exclusion_value = 'testing'
    organization = create_organization(name=exclusion_value)
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='select id from organization_organization',
        exclude_field=exclusion_key,
        fix_me_link=exclusion_key,
    )
    organization_monitor = create_organization_monitor(
        organization, monitor, status=MonitorInstanceStatus.NO_DATA_DETECTED
    )
    run(organization_monitor)
    result = MonitorResult.objects.get(organization_monitor=organization_monitor).result
    assert len(result['variables']) == 1
    assert result['variables'][0][exclusion_key] == exclusion_value


def test_select_replacement():
    query = '''
    select * from gcp_sql_database_instance gsdi
    where ip_configuration -> '[{"neme": "internet", "value": "0.0.0.0/0"}]'
    '''
    exclude = 'gcp_sql_database_instance.akas'

    new_query = build_query_for_variables(query, '', exclude)

    expected_alias = f'{TEMPLATE_PREFIX}_gcp_sql_database_instance__akas'
    expected = (
        f'select *, gsdi.akas as {expected_alias} from gcp_sql_database_instance gsdi'
    )
    assert new_query.strip().startswith(expected)


def test_select_json():
    query = '''
    select c1, c2 -> 'attr'
    as attr from gcp_table gci
    '''
    exclude = 'gcp_table.akas'
    new_query = build_query_for_variables(query, '', exclude)
    expected = f'''
    select c1, c2 -> 'attr'
    as attr, gci.akas as {TEMPLATE_PREFIX}_gcp_table__akas from gcp_table gci
    '''
    assert new_query.strip() == expected.strip()


def test_raw_selected_columns_json():
    query = '''
    select c1, c2 -> 'attr'
    as attr from gcp_table gci
    '''
    columns = get_raw_selected_columns(query)
    expected = '''
    c1, c2 -> 'attr'
    as attr
    '''
    assert columns.strip() == expected.strip()
