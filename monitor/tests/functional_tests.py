import json
from collections import OrderedDict
from concurrent.futures import Future
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from moto import mock_dynamodb, mock_iam, mock_organizations, mock_sts

from control.tests.factory import create_control
from integration.encryption_utils import encrypt_value
from integration.models import SUCCESS
from integration.tests import create_connection_account
from monitor.constants import UNWATCH, WATCH
from monitor.models import (
    Monitor,
    MonitorExclusion,
    MonitorExclusionEvent,
    MonitorExclusionEventType,
    MonitorHealthCondition,
    MonitorInstanceStatus,
    MonitorResult,
    MonitorStatus,
    MonitorSubscriptionEvent,
    MonitorSubscriptionEventType,
    MonitorType,
    MonitorUrgency,
    MonitorUserEvent,
    MonitorUserEventsOptions,
    OrganizationMonitor,
)
from monitor.result import Result
from monitor.runner import exclude_results, run
from monitor.schema import get_watchers
from monitor.steampipe_configurations.aws import get_aws_configuration
from monitor.steampipe_configurations.azure import get_azure_configuration
from monitor.steampipe_configurations.heroku import get_heroku_configuration
from monitor.steampipe_configurations.okta import get_okta_configuration
from monitor.tasks import (
    clear_monitor_exclusions,
    create_monitors_and_run,
    run_monitors,
    update_monitors,
)
from monitor.template import TEMPLATE_PREFIX
from monitor.tests.factory import (
    create_monitor,
    create_monitor_exclusion,
    create_monitor_result,
    create_organization_monitor,
    create_subtask,
)
from monitor.tests.queries import GET_MONITORS_FILTERS
from monitor.types import ADMIN_ROLE, CONTRIBUTOR_ROLE
from monitor.validators import validate_subtask_reference
from organization.tests import create_organization
from program.tests.factory import create_task
from tag.tests.functional_tests import create_tags
from user.constants import ACTIVE
from user.tests.factory import create_user

ADMIN_HEYLAIKA_COM = 'admin@heylaika.com'

MONITORS_MONITOR_ID = 'monitors.monitor_id'

CONTROLS_ID = 'controls.id'

MONITOR_TEST = 'Monitor Test'

FAKE_CLIENT_ARN = 'arn:aws:iam::209990397144:role/fake'
TEST_QUERY = 'SELECT id, name FROM organization_organization WHERE id= %s'
TEST_AWS_QUERY = 'SELECT * FROM aws_s3_bucket WHERE id= %s'
EMPTY_QUERY = 'SELECT id, name FROM organization_organization where id<0'
TEST_MONITOR_NAME = 'Test Monitor 1'

GET_ORGANIZATION_MONITORS = '''
        query organizationMonitors($filter: JSONString, $searchCriteria:
        String) {
          organizationMonitors(filter: $filter, searchCriteria:
          $searchCriteria) {
            results {
              id
              organizationId
              displayId
              monitor {
                name
                query
                description
                monitorType
                status
                healthCondition
                frequency
                runnerType
                sourceSystems
              }
              urgency
              lastRun
              active
              status
              isUserWatching
            }
            stats {
              actives
              inactives
              activesFlagged
              isUserSubscribed
              canUserSubscribe
            }
            events {
              showBanner
            }
          }
        }
    '''

GET_ORGANIZATION_MONITOR = '''
        query organizationMonitor(
            $id: String,
        ) {
          organizationMonitor(
            id: $id,
          ) {
              id
              organizationId
              monitor {
                name
                query
                description
                monitorType
                status
                healthCondition
                frequency
                runnerType
                excludeField
              }
              controls {
                name
                displayId
              }
              tags {
                id
                name
              }
              lastResult {
                id
                createdAt
                result
                status
                fixMeLinks
                canExclude
              }
              timeline {
                start
                end
                status
              }
              watcherList {
                id
                watchers {
                  id
                  firstName
                  lastName
                }
              }
              lastRun
              active
              status
              exclusionQuery
            }
        }
    '''

GET_CONTROL_MONITORS = '''
  query controlMonitors($filter: JSONString) {
    controlMonitors(filter: $filter) {
      results {
        id
        monitor {
          id
          name
          status
          monitorType
          parentMonitor
        }
        lastRun
        active
        status
      }
      controlStats {
        actives
        inactives
      }
      pagination {
        current
        pageSize
        total
      }
      __typename
    }
  }
  '''

GET_WATCHER_LIST = '''
  query watcherList($id: ID!) {
    watcherList(id: $id) {
      id
      watchers {
        id
        firstName
        lastName
      }
    }
  }
  '''

UPDATE_ORGANIZATION_MONITOR = '''
    mutation($id: String!, $active: Boolean) {
      updateOrganizationMonitor(id: $id, active: $active)
        {
          organizationMonitor {
            id
            monitor {
              name
              query
              description
              monitorType
              status
              healthCondition
              frequency
              runnerType
            }
            lastRun
            active
            status
          }
        }
    }
    '''

EXECUTE_ORGANIZATION_MONITOR = '''
    mutation($id: String!) {
      executeOrganizationMonitor(id: $id)
        {
          organizationMonitor {
            id
            monitor {
              name
              query
              description
              monitorType
              status
              healthCondition
              frequency
              runnerType
            }
            lastRun
            active
            status
          }
        }
    }
    '''

CLONE_MONITOR = '''
    mutation(
      $id: String!,
      $name: String,
      $description: String,
      $query: String
    ) {
      updateMonitor(
        id: $id,
        name: $name,
        description: $description,
        query: $query
      )
        {
          organizationMonitor {
            id
            monitor {
              id
              name
              query
              description
              monitorType
              status
              healthCondition
              frequency
              runnerType
            }
            lastRun
            active
            status
          }
        }
    }
    '''

SUBSCRIBE_TO_WATCHER_LIST = '''
    mutation($id: ID!) {
      subscribeToWatcherList(id: $id) {
        id
        watchers {
          id
          firstName
          lastName
        }
      }
    }
    '''

ADD_CUSTOM_MONITOR_WITHOUT_PARENT = '''
    mutation(
      $name: String!
      $description: String!
      $healthCondition: String!
      $urgency: String!
      $query: String!
    ) {
      addCustomMonitorWithoutParent(
        name: $name
        description: $description
        healthCondition: $healthCondition
        urgency: $urgency
        query: $query
      ) {
        organizationMonitor {
          id
          monitor {
            id
            name
            query
            description
            monitorType
            status
            healthCondition
            frequency
            runnerType
          }
          lastRun
          active
          status
        }
      }
    }
    '''

ORGANIZATION_MONITORS = [
    'organization_monitor_healthy',
    'organization_monitor_inactive_triggered',
    'organization_monitor_no_data',
    'organization_monitor_active_triggered',
]

CONTROL_POLICIES = 'Control X'
CONTROL_DOCUMENTS = 'Control Y'


@pytest.mark.functional
def test_duplicate_organization_monitor_view():
    organization = create_organization(name='Test')
    monitor = create_monitor(name='monitor', query='original_monitor')
    cloned_monitor_name = 'name'
    cloned_monitor_query = 'query'
    cloned_monitor_description = 'description'
    Client().post(
        '/admin/duplicate_monitor',
        {
            'apply': 'Duplicate',
            'organization': organization.id,
            'monitor': monitor.id,
            'name': cloned_monitor_name,
            'query': cloned_monitor_query,
            'description': cloned_monitor_description,
        },
    )
    cloned_monitor = Monitor.objects.filter(
        name=cloned_monitor_name,
        query=cloned_monitor_query,
        description=cloned_monitor_description,
    )
    assert cloned_monitor.exists()
    assert OrganizationMonitor.objects.filter(
        organization=organization, monitor=cloned_monitor.first(), active=True
    )


@pytest.fixture()
def organization_monitor_healthy(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(name=MONITOR_TEST, query='select name from test'),
    )


@pytest.fixture()
def organization_monitor_exclusion(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(
            name=MONITOR_TEST,
            query='select name, id, status from controls',
            exclude_field=CONTROLS_ID,
            health_condition='empty_results',
        ),
    )


@pytest.fixture()
def organization_monitor_inactive_triggered(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(
            name='Test Monitor 2',
            query='SELECT id FROM monitors WHERE id=1',
            status=MonitorStatus.INACTIVE,
        ),
        active=False,
        status=MonitorInstanceStatus.TRIGGERED,
    )


@pytest.fixture()
def organization_monitor_no_data(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(
            name='Test Monitor 3',
            query='select description from test',
            status=MonitorStatus.ACTIVE,
            health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        ),
        active=True,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )


@pytest.fixture()
def organization_monitor_active_triggered(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(
            name='Test Monitor 4',
            query='select status from test',
            status=MonitorStatus.INACTIVE,
        ),
        active=True,
        status=MonitorInstanceStatus.TRIGGERED,
    )


@pytest.fixture()
def organization_monitor_connection_error(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(
            name='Test Monitor 5', query='select name, status from test'
        ),
        active=True,
        status=MonitorInstanceStatus.CONNECTION_ERROR,
    )


def populate_monitor_results(organization_monitor):
    mnt_rslt_healthy = create_monitor_result(
        created_at=datetime.now(), organization_monitor=organization_monitor
    )
    mnt_rslt_triggered = create_monitor_result(
        created_at=datetime.now() - timedelta(days=1),
        organization_monitor=organization_monitor,
        status=MonitorInstanceStatus.TRIGGERED,
    )
    mnt_rslt_no_data = create_monitor_result(
        created_at=datetime.now() - timedelta(days=2),
        organization_monitor=organization_monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    return mnt_rslt_healthy, mnt_rslt_triggered, mnt_rslt_no_data


@pytest.mark.functional(permissions=['monitor.view_monitor'])
@pytest.mark.parametrize("organization_monitor", ORGANIZATION_MONITORS)
def test_get_all_organization_monitors(graphql_client, organization_monitor, request):
    request.getfixturevalue(organization_monitor)
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']['results']
    assert len(organization_monitors) == 1


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_organization_monitor_urgency(
    graphql_client, organization_monitor_healthy, organization_monitor_no_data
):
    organization_monitor_healthy.urgency = MonitorUrgency.URGENT
    organization_monitor_healthy.save()
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']['results']
    assert len(organization_monitors) == 2
    assert organization_monitors[0]['urgency'] == MonitorUrgency.URGENT
    assert (
        organization_monitors[1]['urgency']
        == organization_monitor_no_data.monitor.urgency
    )


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_organization_monitor_with_default_order(
    graphql_client,
    organization_monitor_healthy,
    organization_monitor_active_triggered,
    organization_monitor_inactive_triggered,
    organization_monitor_no_data,
    organization_monitor_connection_error,
):
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']['results']
    assert len(organization_monitors) == 5
    assert organization_monitors[0]['id'] == str(
        organization_monitor_active_triggered.id
    )
    assert organization_monitors[1]['id'] == str(
        organization_monitor_connection_error.id
    )
    assert organization_monitors[2]['id'] == str(organization_monitor_healthy.id)
    assert organization_monitors[3]['id'] == str(organization_monitor_no_data.id)
    assert organization_monitors[4]['id'] == str(
        organization_monitor_inactive_triggered.id
    )


@pytest.mark.functional(permissions=['monitor.view_monitor'])
@pytest.mark.parametrize("organization_monitor", ORGANIZATION_MONITORS)
def test_get_organization_monitors_source_systems_type(
    graphql_client, graphql_organization, organization_monitor, request
):
    org_monitor = request.getfixturevalue(organization_monitor)
    org_monitor.monitor.monitor_type = MonitorType.CUSTOM
    org_monitor.monitor.organization = graphql_organization
    org_monitor.monitor.save()
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']['results']
    for organization_monitor in organization_monitors:
        assert (
            organization_monitor['monitor']['sourceSystems']
            == '["Custom", "Asana", "AWS", "Google Cloud Platform", "Laika App"]'
        )


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_all_organization_monitors_with_search_criteria(
    graphql_client, organization_monitor_healthy
):
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITORS, variables={'searchCriteria': 'Monitor T'}
    )
    organization_monitors = response['data']['organizationMonitors']['results']
    assert len(organization_monitors) == 1
    assert organization_monitors[0]['monitor']['name'] == MONITOR_TEST


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_all_organization_monitors_filtered_by_control(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description='Testing update control',
        implementation_notes='<p>testing controls</p>',
    )
    organization_monitor_healthy.controls.add(control)
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITORS,
        variables={'filter': json.dumps({'controlId': str(control.id)})},
    )
    organization_monitors = response['data']['organizationMonitors']['results']
    assert len(organization_monitors) == 1


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_control_monitors(
    graphql_client,
    graphql_organization,
    organization_monitor_no_data,
    organization_monitor_active_triggered,
    organization_monitor_healthy,
):
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control associated monitors Test',
        description='Testing default order for control associated monitors',
        implementation_notes='<p>testing controls</p>',
    )
    organization_monitor_no_data.controls.add(control)
    organization_monitor_active_triggered.controls.add(control)
    organization_monitor_healthy.controls.add(control)
    response = graphql_client.execute(
        GET_CONTROL_MONITORS,
        variables={
            'filter': json.dumps(
                {
                    'controlId': str(control.id),
                    'triggered': 'triggered',
                    'connectionError': 'connection_error',
                    'active': True,
                }
            )
        },
    )
    control_monintor_expected_controlstats = {'actives': 3, 'inactives': 0}
    response = response['data']['controlMonitors']
    control_monitors = response['results']
    actives = response['controlStats']['actives']
    inactives = response['controlStats']['inactives']
    assert control_monintor_expected_controlstats['actives'] == actives
    assert control_monintor_expected_controlstats['inactives'] == inactives
    assert len(control_monitors) == 1


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_latest_result_from_organization_monitors(
    organization_monitor_healthy,
    graphql_client,
):
    populate_monitor_results(organization_monitor_healthy)
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor_healthy.id}
    )
    org_monitor = response['data']['organizationMonitor']
    latest_result = org_monitor['lastResult']
    fix_links = latest_result['fixMeLinks']
    assert latest_result['status'] == 'no_data_detected'
    assert len(org_monitor['timeline']) == 3
    assert fix_links == []


def add_fix_me_link_to_monitor(organization_monitor, parameter):
    organization_monitor.monitor.fix_me_link = f'/monitors/{parameter}'
    organization_monitor.monitor.save()


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_latest_result_empty(
    organization_monitor_no_data,
    graphql_client,
):
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor_no_data.id}
    )
    org_monitor = response['data']['organizationMonitor']
    latest_result = org_monitor['lastResult']
    assert latest_result is None
    assert len(org_monitor['timeline']) == 1


@pytest.mark.functional
def test_laika_context_runner(temp_context_runner):
    organization = create_organization(name='Test')
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
    )
    org_monitor = create_organization_monitor(
        organization, monitor, status=MonitorInstanceStatus.NO_DATA_DETECTED
    )

    run(org_monitor)

    monitor_result = MonitorResult.objects.first()
    assert monitor_result.status == MonitorInstanceStatus.HEALTHY
    result = monitor_result.result
    print('aaaa', result)
    first_row, *_ = result['data']
    assert first_row == [organization.id.hex, organization.name]
    assert result['columns'] == ['id', 'name']
    assert org_monitor.status == MonitorInstanceStatus.HEALTHY


@pytest.mark.functional
def test_runner_no_data_detected():
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query='SELECT * FROM dummy_table',
        validation_query=EMPTY_QUERY,
    )
    org_monitor = create_organization_monitor(
        create_organization(), monitor, status=MonitorInstanceStatus.HEALTHY
    )

    run(org_monitor)

    assert org_monitor.status == MonitorInstanceStatus.CONNECTION_ERROR


@pytest.mark.functional
def test_runner_with_sql_error(error_logs, temp_context_runner):
    organization = create_organization(name='Test')
    monitor = create_monitor(
        name='Test Monitor',
        query='SELECT id, name FROM wrong_table WHERE id= %s',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    org_monitor = create_organization_monitor(
        organization, monitor, status=MonitorInstanceStatus.NO_DATA_DETECTED
    )
    run(org_monitor)
    monitor.refresh_from_db()
    assert monitor.status == MonitorStatus.ACTIVE
    assert org_monitor.status == MonitorInstanceStatus.CONNECTION_ERROR
    assert OrganizationMonitor.objects.filter(
        status=MonitorInstanceStatus.CONNECTION_ERROR,
    ).exists()
    assert MonitorResult.objects.filter(
        organization_monitor=org_monitor, result__error='no such table: wrong_table'
    ).exists()


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_monitor_results_summary_from_organization_monitors(
    graphql_client,
    organization_monitor_healthy,
    organization_monitor_no_data,
    organization_monitor_inactive_triggered,
    organization_monitor_active_triggered,
):
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    stats = response['data']['organizationMonitors']['stats']
    assert stats['actives'] == 3
    assert stats['inactives'] == 1
    assert stats['activesFlagged'] == 1


@pytest.mark.functional
def test_update_monitors_without_monitor_flag():
    create_organization(name='Test1', state=ACTIVE)
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    update_monitors()
    assert MonitorResult.objects.exists() is True
    assert OrganizationMonitor.objects.exists() is True


@pytest.mark.functional
def test_update_monitors_with_monitor_flag(temp_context_runner):
    create_organization(name='Test X', state=ACTIVE)
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    update_monitors()
    monitor_result = MonitorResult.objects.first()
    assert MonitorResult.objects.exists()
    assert monitor_result.query == TEST_QUERY
    assert OrganizationMonitor.objects.exists()


@pytest.mark.functional
def test_update_monitors_monitor_no_data_detected(
    temp_context_runner,
):
    organization = create_organization(name='Test Y', state=ACTIVE)
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    create_monitor(
        name="TEST_MONITOR_NAME",
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        validation_query=EMPTY_QUERY,
    )
    update_monitors()
    assert len(OrganizationMonitor.objects.filter(organization=organization)) == 1


@pytest.mark.functional
def test_update_monitors_missing_laika_object_type(temp_context_runner):
    create_organization(name='Test X', state=ACTIVE)
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        validation_query='select * from lo_users;',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    update_monitors()
    assert not OrganizationMonitor.objects.exists()


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_no_data_detected_organization_monitor(
    graphql_client, organization_monitor_healthy
):
    resp = graphql_client.execute(
        UPDATE_ORGANIZATION_MONITOR,
        variables={'id': organization_monitor_healthy.id, 'active': False},
    )
    org_mon = resp['data']['updateOrganizationMonitor']['organizationMonitor']
    assert org_mon['active'] is False
    assert MonitorResult.objects.filter(
        status=MonitorInstanceStatus.CONNECTION_ERROR
    ).exists()
    assert not OrganizationMonitor.objects.get(
        id=organization_monitor_healthy.id
    ).toggled_by_system


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def test_aws_configuration(graphql_organization):
    credentials = {"external_role_arn": FAKE_CLIENT_ARN}
    connection_account = create_connection_account(
        'AWS',
        configuration_state={'credentials': credentials, 'aws_region': 'us-east-1'},
        status=SUCCESS,
        organization=graphql_organization,
    )
    configuration = get_aws_configuration("laika", connection_account)

    assert 'connection "laika" {' in configuration
    assert 'plugin    = "aws"' in configuration
    assert 'access_key' in configuration
    assert 'regions' in configuration


@pytest.mark.functional
def test_azure_configuration(graphql_organization):
    credentials = {
        "subscriptionId": "subscription_id_mock",
        "clientId": "client_id_mock",
        "clientSecret": encrypt_value("client_secret_mock"),
        "tenantId": "tenant_id_mock",
    }
    connection_account = create_connection_account(
        'Microsoft Azure',
        configuration_state={'credentials': credentials},
        status=SUCCESS,
        organization=graphql_organization,
    )
    configuration = get_azure_configuration("laika", connection_account)

    assert 'connection "laika" {' in configuration
    assert 'plugin    = "azure"' in configuration
    assert 'subscription_id = "subscription_id_mock"' in configuration
    assert 'client_id = "client_id_mock"' in configuration
    assert 'client_secret = "client_secret_mock"' in configuration
    assert 'tenant_id = "tenant_id_mock"' in configuration


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_execute_organization_monitor(
    graphql_client, graphql_organization, temp_context_runner, sync_pool
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
    )
    om = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.NO_DATA_DETECTED,
    )
    resp = graphql_client.execute(EXECUTE_ORGANIZATION_MONITOR, variables={'id': om.id})
    org_mon = resp['data']['executeOrganizationMonitor']['organizationMonitor']
    assert org_mon['status'] == MonitorInstanceStatus.HEALTHY


@pytest.fixture()
def sync_pool():
    def run_sync(func, *args):
        func(*args)
        return Future()

    with patch('monitor.runner.executor') as pool:
        pool.submit = run_sync
        yield


@pytest.mark.functional
def test_monitors_with_controls(temp_context_runner, control_organization):
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        control_references=f'{CONTROL_POLICIES}\n{CONTROL_DOCUMENTS}',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )

    update_monitors()

    org_monitor = OrganizationMonitor.objects.first()
    assert org_monitor
    assert org_monitor.controls.count() == 2


@pytest.mark.functional
def test_create_monitors_and_run_without_dependencies(control_organization):
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_AWS_QUERY,
        control_references=f'{CONTROL_POLICIES}\n{CONTROL_DOCUMENTS}',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )

    create_monitors_and_run(control_organization)

    assert OrganizationMonitor.objects.exists()
    assert MonitorResult.objects.exists()


@pytest.mark.functional
def test_create_monitors_and_run_dependencies_match(control_organization):
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_AWS_QUERY,
        control_references=f'{CONTROL_POLICIES}\n{CONTROL_DOCUMENTS}',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    dependencies = {"aws_dependency", "lo_users", "lo_accounts"}
    create_monitors_and_run(control_organization, dependencies)

    assert OrganizationMonitor.objects.exists()
    assert MonitorResult.objects.exists()


@pytest.mark.functional
def test_create_monitors_and_run_not_dependencies_match(control_organization):
    create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_AWS_QUERY,
        control_references=f'{CONTROL_POLICIES}\n{CONTROL_DOCUMENTS}',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    dependencies = {"azure_dependency", "lo_users", "lo_accounts"}
    create_monitors_and_run(control_organization, dependencies)

    assert not OrganizationMonitor.objects.exists()
    assert not MonitorResult.objects.exists()


@pytest.mark.functional
def test_monitor_refresh_controls(temp_context_runner, control_organization):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        control_references=f'{CONTROL_POLICIES}\n{CONTROL_DOCUMENTS}',
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    org_monitor = OrganizationMonitor.objects.create(
        organization=control_organization, active=True, monitor=monitor
    )

    monitor.control_references = CONTROL_POLICIES
    monitor.save()

    assert org_monitor.controls.count() == 1
    assert org_monitor.controls.filter(name=CONTROL_POLICIES).exists()


@pytest.mark.functional
def test_monitor_delete_controls(temp_context_runner, control_organization):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        control_references=CONTROL_DOCUMENTS,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )
    org_monitor = OrganizationMonitor.objects.create(
        organization=control_organization, active=True, monitor=monitor
    )

    monitor.control_references = None
    monitor.save()

    assert org_monitor.controls.count() == 0


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_organizations_monitor_control(
    organization_monitor_healthy, graphql_organization, graphql_client
):
    create_control(graphql_organization, 1, CONTROL_POLICIES)
    monitor = organization_monitor_healthy.monitor
    monitor.control_references = CONTROL_POLICIES
    monitor.save()

    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor_healthy.id}
    )
    org_monitor = response['data']['organizationMonitor']
    controls = org_monitor['controls']
    assert controls
    assert controls == [dict(name=CONTROL_POLICIES, displayId='CTRL-1')]


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_organizations_monitor_tag(
    organization_monitor_healthy, graphql_organization, graphql_client
):
    create_tags(graphql_organization)
    monitor = organization_monitor_healthy.monitor
    monitor.tag_references = 'First Tag\nMissing Tag\nMissing Tag'
    monitor.save()

    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor_healthy.id}
    )
    org_monitor = response['data']['organizationMonitor']
    tags = org_monitor['tags']
    assert tags
    assert tags[0] == OrderedDict([('id', '1'), ('name', 'First Tag')])
    assert tags[1] == OrderedDict([('id', '3'), ('name', 'Missing Tag')])


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_clone_monitor_with_all_variables(graphql_client, organization_monitor_healthy):
    monitor_id = organization_monitor_healthy.id
    resp = graphql_client.execute(
        CLONE_MONITOR,
        variables={
            'id': monitor_id,
            'name': 'Devices',
            'description': 'New Description after change',
            'query': TEST_QUERY,
        },
    )
    org_monitor = resp['data']['updateMonitor']['organizationMonitor']
    monitor = resp['data']['updateMonitor']['organizationMonitor']['monitor']
    assert monitor['monitorType'] == MonitorType.CUSTOM
    assert org_monitor['monitor']['id'] != str(monitor_id)


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_clone_monitor_with_one_variable(graphql_client, organization_monitor_healthy):
    monitor_id = organization_monitor_healthy.id
    resp = graphql_client.execute(
        CLONE_MONITOR, variables={'id': monitor_id, 'query': TEST_QUERY}
    )
    org_monitor = resp['data']['updateMonitor']['organizationMonitor']
    monitor = resp['data']['updateMonitor']['organizationMonitor']['monitor']
    assert monitor['monitorType'] == MonitorType.CUSTOM
    assert org_monitor['monitor']['id'] != str(monitor_id)


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_clone_monitor_monitor_results_copied(
    graphql_client, organization_monitor_healthy
):
    populate_monitor_results(organization_monitor_healthy)
    monitor_id = organization_monitor_healthy.monitor.id
    resp = graphql_client.execute(
        CLONE_MONITOR, variables={'id': monitor_id, 'query': TEST_QUERY}
    )
    org_monitor = resp['data']['updateMonitor']['organizationMonitor']
    assert MonitorResult.objects.filter(
        organization_monitor_id=org_monitor['id']
    ).exists()
    assert org_monitor['monitor']['id'] != str(monitor_id)


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_edit_monitor_with_some_variables(graphql_client, organization_monitor_no_data):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        control_references=CONTROL_DOCUMENTS,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
        monitor_type=MonitorType.CUSTOM,
        organization=organization_monitor_no_data.organization,
    )
    organization_monitor_no_data.monitor = monitor
    organization_monitor_no_data.save()
    resp = graphql_client.execute(
        CLONE_MONITOR, variables={'id': monitor.id, 'name': 'new name'}
    )
    org_monitor = resp['data']['updateMonitor']['organizationMonitor']
    monitor = resp['data']['updateMonitor']['organizationMonitor']['monitor']
    assert monitor['name'] != TEST_MONITOR_NAME
    assert org_monitor['id'] == str(organization_monitor_no_data.id)


@pytest.fixture()
def control_organization():
    organization = create_organization(name='Test Z', state=ACTIVE)
    create_control(organization, 1, CONTROL_POLICIES)
    create_control(organization, 2, CONTROL_DOCUMENTS)
    return organization


@pytest.mark.functional
def test_run_monitors_with_dependencies(organization_monitor_healthy):
    run_monitors(
        organization_monitor_healthy.organization_id, dependencies={'aws_integration'}
    )
    assert not MonitorResult.objects.exists()


@pytest.mark.functional
def test_run_all_monitors(organization_monitor_healthy):
    run_monitors(organization_monitor_healthy.organization_id)
    assert MonitorResult.objects.exists()


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_organization_monitor_display_id(graphql_client, graphql_organization):
    monitor1 = create_monitor(
        name='Monitor Test1', query='select * from events', display_id='LAO-1'
    )
    monitor2 = create_monitor(
        name='Monitor Test2', query='select * from people;', display_id='LAO-2'
    )
    create_organization_monitor(organization=graphql_organization, monitor=monitor1)
    create_organization_monitor(organization=graphql_organization, monitor=monitor2)
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITORS,
    )
    organization_monitors = response['data']['organizationMonitors']['results']

    assert organization_monitors[0]['displayId'] == 'LAO-1'
    assert organization_monitors[1]['displayId'] == 'LAO-2'


NUMBER_OF_USERS = 5


@pytest.fixture
def users(graphql_organization):
    users = []
    for index in range(0, NUMBER_OF_USERS):
        users.append(
            create_user(
                graphql_organization,
                first_name='User',
                last_name=index,
                username=f'user_{index}',
                email=f'user_{index}@heylaika.com',
            )
        )
    return users


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_watcher_list_with_users(
    users, graphql_client, graphql_organization, organization_monitor_healthy
):
    watcher_list = organization_monitor_healthy.watcher_list
    watcher_list.users.set(users)
    response = graphql_client.execute(
        GET_WATCHER_LIST, variables={'id': watcher_list.id}
    )
    data = response['data']['watcherList']
    watchers = data['watchers']
    assert 'errors' not in response
    assert len(watchers) == NUMBER_OF_USERS


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_watcher_list_with_no_users(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    watcher_list = organization_monitor_healthy.watcher_list
    watcher_list.users.set([])
    response = graphql_client.execute(
        GET_WATCHER_LIST, variables={'id': watcher_list.id}
    )
    data = response['data']['watcherList']
    watchers = data['watchers']
    assert 'errors' not in response
    assert len(watchers) == 0


@pytest.mark.functional(permissions=['user.view_user'])
def test_subscribe_to_organization_monitors(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    user = graphql_client.context.get('user')
    watcher_list = organization_monitor_healthy.watcher_list
    watcher_list.users.set([])
    response = graphql_client.execute(
        SUBSCRIBE_TO_WATCHER_LIST, variables={'id': watcher_list.id}
    )
    watchers = response['data']['subscribeToWatcherList']['watchers']
    assert 'errors' not in response
    assert len(watchers) == 1
    assert watchers[0]['id'] == str(user.id)
    assert watchers[0]['firstName'] == f'{user.first_name}'
    assert watchers[0]['lastName'] == f'{user.last_name}'


@pytest.mark.functional(permissions=['user.view_user'])
def test_subscribe_to_organization_monitor_without_watcher_list(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    user = graphql_client.context.get('user')
    response = graphql_client.execute(
        SUBSCRIBE_TO_WATCHER_LIST,
        variables={'id': organization_monitor_healthy.watcher_list.id},
    )
    watchers = response['data']['subscribeToWatcherList']['watchers']
    assert 'errors' not in response
    assert len(watchers) == 1
    assert watchers[0]['id'] == str(user.id)
    assert watchers[0]['firstName'] == f'{user.first_name}'
    assert watchers[0]['lastName'] == f'{user.last_name}'


@pytest.mark.functional(permissions=['user.view_user'])
def test_unsubscribe_to_organization_monitors(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    user = graphql_client.context.get('user')
    watcher_list = organization_monitor_healthy.watcher_list
    watcher_list.users.set([user])
    response = graphql_client.execute(
        SUBSCRIBE_TO_WATCHER_LIST, variables={'id': watcher_list.id}
    )
    watchers = response['data']['subscribeToWatcherList']['watchers']
    assert 'errors' not in response
    assert len(watchers) == 0


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_watcher_list_with_users_unauthorized(
    users, graphql_client, graphql_organization, organization_monitor_healthy
):
    organization_monitor = create_organization_monitor()
    watcher_list = organization_monitor.watcher_list
    watcher_list.users.set(users)
    response = graphql_client.execute(
        GET_WATCHER_LIST, variables={'id': watcher_list.id}
    )
    assert 'errors' in response
    assert 'Not found' in response['errors'][0]['message']


@pytest.mark.functional(permissions=['user.view_user'])
def test_subscribe_to_organization_monitor_unauthorized(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    organization_monitor = create_organization_monitor()
    response = graphql_client.execute(
        SUBSCRIBE_TO_WATCHER_LIST,
        variables={'id': organization_monitor.watcher_list.id},
    )
    assert 'errors' in response
    assert 'Not found' in response['errors'][0]['message']


@pytest.mark.functional
def test_watcher_list_assignment_after_organization_monitor_change():
    organization = create_organization(name='Test')
    admin = create_user(
        organization, email=ADMIN_HEYLAIKA_COM, role='OrganizationAdmin'
    )
    organization_monitor = create_organization_monitor(organization=organization)
    watcher_list = organization_monitor.watcher_list
    assert watcher_list.users.count() == 1
    assert watcher_list.users.filter(id=admin.id).exists()


@pytest.mark.functional
def test_watcher_list_assignment_after_organization_monitor_change_no_users():
    organization = create_organization(name='Test')
    organization_monitor = create_organization_monitor(organization=organization)
    watcher_list = organization_monitor.watcher_list
    assert watcher_list.users.count() == 0


@pytest.mark.functional
def test_watcher_list_assignment_after_user_change_to_admin():
    organization = create_organization(name='Test')
    organization_monitor = create_organization_monitor(organization=organization)
    watcher_list = organization_monitor.watcher_list
    admin = create_user(
        organization, email=ADMIN_HEYLAIKA_COM, role='OrganizationAdmin'
    )
    assert watcher_list.users.count() == 1
    assert watcher_list.users.filter(id=admin.id).exists()


@pytest.mark.functional
def test_watcher_list_assignment_after_user_change_to_viewer():
    organization = create_organization(name='Test')
    admin = create_user(
        organization, email=ADMIN_HEYLAIKA_COM, role='OrganizationAdmin'
    )
    contributor = create_user(
        organization, email='contributor@heylaika.com', role='OrganizationMember'
    )
    organization_monitor = create_organization_monitor(organization=organization)
    watcher_list = organization_monitor.watcher_list
    admin.role = 'OrganizationViewer'
    admin.save()
    contributor.role = 'OrganizationViewer'
    contributor.save()
    assert watcher_list.users.count() == 0


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_add_custom_monitor_without_parent(
    graphql_client, graphql_organization, temp_context_runner, sync_pool
):
    response = graphql_client.execute(
        ADD_CUSTOM_MONITOR_WITHOUT_PARENT,
        variables={
            'name': 'custom_monitor_1',
            'description': 'custom monitor without parent',
            'healthCondition': MonitorHealthCondition.RETURN_RESULTS,
            'urgency': MonitorUrgency.LOW,
            'query': 'select *  from controls',
        },
    )
    result = response['data']['addCustomMonitorWithoutParent']
    organization_monitor = result['organizationMonitor']
    assert 'errors' not in response
    assert len(result) == 1
    assert MonitorResult.objects.filter(
        organization_monitor_id=organization_monitor['id']
    ).exists()


GET_UNFILTERED_ORGANIZATION_MONITOR_RESULT = '''
        query unfilteredOrganizationMonitorResult (
          $organizationMonitorId: ID!,
          $limit: Int!
        ) {
          unfilteredOrganizationMonitorResult (
            organizationMonitorId: $organizationMonitorId,
            limit: $limit
          ) {
            result
            fixMeLinks
          }
        }
    '''


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_unfiltered_organization_monitor_result(
    graphql_client,
    graphql_organization,
    temp_context_runner,
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
    response = graphql_client.execute(
        GET_UNFILTERED_ORGANIZATION_MONITOR_RESULT,
        variables={
            'organizationMonitorId': organization_monitor.id,
            'limit': 10,
        },
    )
    result = response['data']['unfilteredOrganizationMonitorResult']['result']
    fix_me_links = response['data']['unfilteredOrganizationMonitorResult']['fixMeLinks']
    assert 'error' not in result
    assert result is not None
    assert fix_me_links is not None


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_unfiltered_organization_monitor_result_with_fixme_links(
    graphql_client,
    graphql_organization,
    temp_context_runner,
):
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.RETURN_RESULTS,
        fix_me_link='organization/$organization_organization.id',
        exclude_field='organization_organization.id',
    )
    organization_monitor = create_organization_monitor(
        graphql_organization,
        monitor,
        status=MonitorInstanceStatus.TRIGGERED,
    )
    response = graphql_client.execute(
        GET_UNFILTERED_ORGANIZATION_MONITOR_RESULT,
        variables={
            'organizationMonitorId': organization_monitor.id,
            'limit': 10,
        },
    )
    result = response['data']['unfilteredOrganizationMonitorResult']['result']
    fix_me_links = response['data']['unfilteredOrganizationMonitorResult']['fixMeLinks']
    assert 'error' not in result
    assert result is not None
    assert len(fix_me_links) > 0


DRY_QUERY_RUN = '''
        query dryQueryRun ($query: String!) {
          dryQueryRun (query: $query) {
            result
          }
        }
    '''


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_dry_query(
    graphql_client,
    graphql_organization,
    temp_context_runner,
):
    response = graphql_client.execute(DRY_QUERY_RUN, variables={'query': TEST_QUERY})
    result = response['data']['dryQueryRun']['result']
    assert 'error' not in result
    assert result is not None


@pytest.mark.functional
def test_exclude_skip_missing_variable(organization_monitor_healthy):
    MonitorExclusion.objects.create(
        organization_monitor=organization_monitor_healthy,
        is_active=True,
        key=MONITORS_MONITOR_ID,
        value='1',
        snapshot=[''],
    )
    result = Result(columns=['monitor_id'], data=[['1']])
    response = exclude_results(organization_monitor_healthy, result)
    assert response.data == [['1']]


@pytest.mark.functional
def test_exclude_filter_by_variable(organization_monitor_healthy):
    MonitorExclusion.objects.create(
        organization_monitor=organization_monitor_healthy,
        is_active=True,
        key=MONITORS_MONITOR_ID,
        value='1',
        snapshot=[''],
    )
    result = Result(
        columns=[f'{TEMPLATE_PREFIX}_monitors__monitor_id', 'id'],
        data=[['1', '2']],
        variables=[{MONITORS_MONITOR_ID: '1'}],
    )
    response = exclude_results(organization_monitor_healthy, result)
    assert response.data == []


@pytest.mark.functional
@pytest.mark.parametrize(
    'new_exclusion, old_exclusion',
    [
        [
            'people.first_name',
            'people.last_name',
        ],
        [
            'people.people_id',
            'lo_user.id',
        ],
    ],
)
def test_valid_exclusion_deprecation(new_exclusion, old_exclusion):
    monitor = create_monitor(name='test', query='testing', exclude_field=new_exclusion)
    for i in range(2):
        create_monitor_exclusion(
            organization_monitor=create_organization_monitor(
                monitor=monitor, organization=create_organization(name=f'Org-{i}')
            ),
            **{j: j for j in ['key', 'value', 'snapshot', 'justification']},
        )
    monitor.exclude_field = old_exclusion
    monitor.save()
    exclusions = MonitorExclusion.objects.filter(organization_monitor__monitor=monitor)
    assert exclusions.filter(is_active=True).count() == 0
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__in=exclusions,
            event_type=MonitorExclusionEventType.DELETED,
        ).count()
        == 2
    )


@pytest.mark.functional
def test_invalid_exclusion_deprecation():
    exclusion = 'people.people_id'
    monitor = create_monitor(name='test', query='', exclude_field=exclusion)
    for i in range(2):
        create_monitor_exclusion(
            organization_monitor=create_organization_monitor(
                monitor=monitor, organization=create_organization(name=i)
            ),
            key=exclusion,
            **{j: j for j in ['value', 'snapshot', 'justification']},
        )
    monitor.save()
    exclusions = MonitorExclusion.objects.filter(organization_monitor__monitor=monitor)
    assert exclusions.filter(is_active=True).count() == 2
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__in=exclusions,
            event_type=MonitorExclusionEventType.DELETED,
        ).count()
        == 0
    )
    assert (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__in=exclusions,
        ).count()
        == 2
    )


@pytest.mark.functional
@pytest.mark.parametrize(
    'creation_date, result, exclusions',
    [
        [datetime.now() - timedelta(days=400), False, 0],
        [datetime.now(), True, 1],
    ],
)
def test_clear_monitor_exclusions(creation_date, result, exclusions):
    field = CONTROLS_ID
    monitor = create_monitor(name='test', query='', exclude_field=field)
    exclusion = create_monitor_exclusion(
        organization_monitor=create_organization_monitor(
            monitor=monitor, organization=create_organization(name='X Org')
        ),
        key=field,
        is_active=False,
        **{j: j for j in ['value', 'snapshot', 'justification']},
    )
    MonitorExclusionEvent.objects.all().delete()
    event = MonitorExclusionEvent.objects.create(
        monitor_exclusion=exclusion,
        justification=exclusion.justification,
        event_type=MonitorExclusionEventType.DELETED,
    )
    MonitorExclusionEvent.objects.filter(monitor_exclusion=exclusion).update(
        event_date=creation_date
    )
    event_id = event.id
    clear_monitor_exclusions()
    assert MonitorExclusion.objects.filter(id=exclusion.id).count() == exclusions
    assert MonitorExclusionEvent.objects.filter(id=event_id).exists() is result


@pytest.mark.functional(permissions=['monitor.view_monitor'])
def test_get_exclusion_query(graphql_client, organization_monitor_exclusion):
    field = CONTROLS_ID
    populate_monitor_results(organization_monitor_exclusion)
    create_monitor_exclusion(
        organization_monitor=organization_monitor_exclusion,
        key=field,
        value='3',
        **{j: j for j in ['snapshot', 'justification']},
    )
    create_monitor_exclusion(
        organization_monitor=organization_monitor_exclusion,
        key=field,
        value='4',
        **{j: j for j in ['snapshot', 'justification']},
    )
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITOR, variables={'id': organization_monitor_exclusion.id}
    )
    expected_exclusion_query = (
        "select name, id, status from controls WHERE controls.id NOT IN ('3', '4')"
    )
    organization_monitor = response['data']['organizationMonitor']
    assert expected_exclusion_query == organization_monitor['exclusionQuery']


@pytest.mark.functional
@pytest.mark.parametrize(
    "subtask_reference, monitor_type, match",
    [
        (
            'a7c05c0b-4611-4b2e-89f0-1ff3e0b7d7b4\n'
            '79f1a6f3-6acd-47d3-91c7-f94a726283e0',
            MonitorType.SYSTEM,
            'All referenced ids must exist.',
        ),
        (
            '75bb86f5-4e1c-401f-a4d3-c6b39e305d3a',
            MonitorType.CUSTOM,
            'Only a system monitor can reference subtasks.',
        ),
    ],
)
def test_validate_subtask_reference_exception_raised(
    subtask_reference, monitor_type, match
):
    with pytest.raises(ValidationError, match=match):
        validate_subtask_reference(subtask_reference, monitor_type)


@pytest.mark.functional
def test_validate_subtask_reference():
    uuid = '100baaf7-43d4-4bad-b41b-ee74d4d74156'
    organization = create_organization()
    create_subtask(
        user=create_user(organization=organization),
        task=create_task(organization=organization),
        reference_id=uuid,
    )
    validate_subtask_reference(uuid, MonitorType.SYSTEM)


ADD_USER_MONITOR_EVENT = '''
    mutation (
      $event: String!
    ) {
      addUserMonitorEvent(
        event: $event
      )
      {
        organizationMonitor{
            id
        }
        event
        user{
          id
        }
        eventTime
      }
    }
    '''


@pytest.mark.functional(permissions=['monitor.change_monitor'])
def test_add_monitor_user_event(
    graphql_client,
    graphql_organization,
    temp_context_runner,
):
    response = graphql_client.execute(
        ADD_USER_MONITOR_EVENT,
        variables={'event': MonitorUserEventsOptions.VIEW_DASHBOARD},
    )
    result = response['data']['addUserMonitorEvent']
    user = result['user']
    assert 'errors' not in response
    assert MonitorUserEvent.objects.filter(user_id=user['id']).exists()


@pytest.mark.functional()
def test_get_monitor_filters(
    graphql_client,
    organization_monitor_healthy,
):
    organization_monitor_healthy.monitor.source_systems = ['aws', 'lo_accounts']
    organization_monitor_healthy.monitor.save()

    response = graphql_client.execute(GET_MONITORS_FILTERS)
    filters = response['data']['monitorsFilters']

    assert len(filters) == 3
    assert filters[2]['items'][0]['name'] == 'AWS'
    assert filters[2]['items'][1]['name'] == 'Laika App'


ORGANIZATION_MONITOR_ACTIVE_STATUSES = [MonitorStatus.ACTIVE, MonitorStatus.INACTIVE]


@pytest.mark.functional(permissions=['monitor.view_monitor'])
@pytest.mark.parametrize('active', ORGANIZATION_MONITOR_ACTIVE_STATUSES)
def test_filter_organization_monitors_by_active(
    graphql_client, graphql_organization, active
):
    expected = active == MonitorStatus.ACTIVE
    for active_status in ORGANIZATION_MONITOR_ACTIVE_STATUSES:
        create_organization_monitor(
            organization=graphql_organization,
            monitor=create_monitor(
                name=f'{active_status} monitor',
                query='select * from organization_organization',
            ),
            active=active_status == MonitorStatus.ACTIVE,
        )
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITORS,
        variables={'filter': json.dumps({'active': [active]})},
    )
    get_all_response = graphql_client.execute(
        GET_ORGANIZATION_MONITORS,
        variables={
            'filter': json.dumps({'active': ORGANIZATION_MONITOR_ACTIVE_STATUSES})
        },
    )
    organization_monitors = response['data']['organizationMonitors']['results']
    all_organization_monitors = get_all_response['data']['organizationMonitors'][
        'results'
    ]
    assert len(organization_monitors) == 1
    assert organization_monitors[0]['active'] == expected
    assert len(all_organization_monitors) == 2


ORGANIZATION_MONITOR_STATUSES = [
    MonitorInstanceStatus.HEALTHY,
    MonitorInstanceStatus.TRIGGERED,
    MonitorInstanceStatus.NO_DATA_DETECTED,
    MonitorInstanceStatus.CONNECTION_ERROR,
]


@pytest.mark.functional(permissions=['monitor.view_monitor'])
@pytest.mark.parametrize('status', ORGANIZATION_MONITOR_STATUSES)
def test_filter_organization_monitors_by_status(
    graphql_client,
    graphql_organization,
    status,
):
    for status in ORGANIZATION_MONITOR_STATUSES:
        create_organization_monitor(
            organization=graphql_organization,
            monitor=create_monitor(
                name=f'{status} monitor',
                query='select * from organization_organization',
            ),
            status=status,
        )
    response = graphql_client.execute(
        GET_ORGANIZATION_MONITORS,
        variables={'filter': json.dumps({'status': [status]})},
    )
    get_all_response = graphql_client.execute(
        GET_ORGANIZATION_MONITORS,
        variables={'filter': json.dumps({'status': ORGANIZATION_MONITOR_STATUSES})},
    )
    organization_monitors = response['data']['organizationMonitors']['results']
    all_organization_monitors = get_all_response['data']['organizationMonitors'][
        'results'
    ]
    assert len(organization_monitors) == 1
    assert organization_monitors[0]['status'] == status
    assert len(all_organization_monitors) == 4


GET_MONITORS_WATCHERS = '''
  query monitorsWatchers {
    monitorsWatchers {
      watchers {
        id
        firstName
        lastName
      }
    }
  }
  '''


def set_watcher_list(organization_monitor, users):
    organization_monitor.watcher_list.users.set(users)


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_monitor_watcher_list_remove(
    users, graphql_client, graphql_organization, organization_monitor_healthy
):
    user = users[0]
    set_watcher_list(organization_monitor_healthy, users)
    organization_monitor_healthy.watcher_list.users.remove(user)
    response = graphql_client.execute(GET_MONITORS_WATCHERS)
    watchers = response['data']['monitorsWatchers']['watchers']
    ids = [w.get('id') for w in watchers]
    assert 'errors' not in response
    assert user.id not in ids
    assert len(set(ids)) == len(ids)


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_monitor_watchers_from_multiple_watcher_list(
    users,
    graphql_organization,
    organization_monitor_healthy,
    organization_monitor_active_triggered,
):
    set_watcher_list(organization_monitor_healthy, users)
    set_watcher_list(organization_monitor_active_triggered, users)
    watchers = get_watchers(graphql_organization)
    ids = [w.id for w in watchers]
    assert len(set(ids)) == len(ids)


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_organization_monitors_with_user_subscribed(
    graphql_client,
    graphql_organization,
):
    user = graphql_client.context.get('user')
    MonitorSubscriptionEvent.objects.create(
        organization=graphql_organization,
        user=user,
        event_type=MonitorSubscriptionEventType.SUBSCRIBED,
    )
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']
    is_user_subscribed = organization_monitors['stats']['isUserSubscribed']
    assert is_user_subscribed


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_organization_monitors_with_user_unsubscribed(
    graphql_client,
    graphql_organization,
):
    user = graphql_client.context.get('user')
    MonitorSubscriptionEvent.objects.create(
        organization=graphql_organization,
        user=user,
        event_type=MonitorSubscriptionEventType.UNSUBSCRIBED,
    )
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']
    is_user_subscribed = organization_monitors['stats']['isUserSubscribed']
    assert not is_user_subscribed


@pytest.fixture
def admin_user(graphql_organization):
    return create_user(
        graphql_organization,
        first_name='Admin',
        last_name='User',
        username='admin_user',
        email='admin_user@heylaika.com',
        role=ADMIN_ROLE,
    )


NON_DEFAULT_ROLE = 'OrganizationViewer'


@pytest.fixture
def non_default_user(graphql_organization):
    return create_user(
        graphql_organization,
        first_name='Non-Default',
        last_name='User',
        username='non_default_user',
        email='non_default_user@heylaika.com',
        role=NON_DEFAULT_ROLE,
    )


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_watcher_assignment_non_default_subscribed(
    graphql_organization, non_default_user
):
    MonitorSubscriptionEvent.objects.create(
        organization=graphql_organization,
        user=non_default_user,
        event_type=MonitorSubscriptionEventType.SUBSCRIBED,
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization
    )
    watchers = organization_monitor.watcher_list.users
    assert watchers.filter(id=non_default_user.id).exists()


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_watcher_assignment_default_unsubscribed(graphql_organization, admin_user):
    MonitorSubscriptionEvent.objects.create(
        organization=graphql_organization,
        user=admin_user,
        event_type=MonitorSubscriptionEventType.UNSUBSCRIBED,
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization
    )
    watchers = organization_monitor.watcher_list.users
    assert not watchers.filter(id=admin_user.id).exists()


SUBSCRIBE_TO_MONITORS = '''
    mutation($eventType: EventType!) {
      subscribeToMonitors(eventType: $eventType) {
        eventType
      }
    }
    '''


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_subscribe_user_to_monitors(
    graphql_client,
    graphql_organization,
):
    user = graphql_client.context.get('user')
    organization_monitor = create_organization_monitor(
        organization=graphql_organization
    )
    watchers = organization_monitor.watcher_list.users
    set_watcher_list(organization_monitor, [])
    response = graphql_client.execute(
        SUBSCRIBE_TO_MONITORS,
        variables={'eventType': MonitorSubscriptionEventType.SUBSCRIBED},
    )
    event_type = response['data']['subscribeToMonitors']['eventType']
    assert event_type == MonitorSubscriptionEventType.SUBSCRIBED
    assert watchers.filter(id=user.id).exists()
    assert MonitorSubscriptionEvent.objects.filter(
        organization=graphql_organization,
        user=user,
        event_type=MonitorSubscriptionEventType.SUBSCRIBED,
    ).exists()


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_unsubscribe_user_from_monitors(
    graphql_client,
    graphql_organization,
    admin_user,
):
    user = graphql_client.context.get('user')
    organization_monitor = create_organization_monitor(
        organization=graphql_organization
    )
    watchers = organization_monitor.watcher_list.users
    set_watcher_list(organization_monitor, [user])
    response = graphql_client.execute(
        SUBSCRIBE_TO_MONITORS,
        variables={'eventType': MonitorSubscriptionEventType.UNSUBSCRIBED},
    )
    event_type = response['data']['subscribeToMonitors']['eventType']
    assert event_type == MonitorSubscriptionEventType.UNSUBSCRIBED
    assert not watchers.filter(id=user.id).exists()
    assert MonitorSubscriptionEvent.objects.filter(
        organization=graphql_organization,
        user=user,
        event_type=MonitorSubscriptionEventType.UNSUBSCRIBED,
    ).exists()


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
@pytest.mark.parametrize('role', [ADMIN_ROLE, CONTRIBUTOR_ROLE])
def test_get_organization_monitors_user_can_subscribe(
    graphql_client, graphql_organization, role
):
    user = graphql_client.context.get('user')
    user.role = role
    user.save()
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']
    can_user_subscribe = organization_monitors['stats']['canUserSubscribe']
    assert can_user_subscribe


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_organization_monitors_user_cannot_subscribe(
    graphql_client,
    graphql_organization,
):
    user = graphql_client.context.get('user')
    user.role = NON_DEFAULT_ROLE
    user.save()
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']
    can_user_subscribe = organization_monitors['stats']['canUserSubscribe']
    assert not can_user_subscribe


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_organization_monitors_user_is_watching(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    user = graphql_client.context.get('user')
    organization_monitor_healthy.watcher_list.users.set([user])
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']['results']
    is_user_watching = organization_monitors[0]['isUserWatching']
    assert is_user_watching


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_organization_monitors_user_is_not_watching(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    organization_monitor_healthy.watcher_list.users.set([])
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']['results']
    is_user_watching = organization_monitors[0]['isUserWatching']
    assert not is_user_watching


BULK_SUBSCRIPTION_TO_MANY_MONITORS = '''
     mutation($input: BulkWatchInput!) {
      bulkWatchMonitors(input: $input) {
        eventType
      }
    }
    '''


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_bulk_unwatch_monitors(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    user = graphql_client.context.get('user')
    organization_monitor_healthy.watcher_list.users.add(user)
    response = graphql_client.execute(
        BULK_SUBSCRIPTION_TO_MANY_MONITORS,
        variables={
            'input': {'eventType': UNWATCH, 'ids': [organization_monitor_healthy.id]}
        },
    )
    organization_monitor_healthy.watcher_list.refresh_from_db()
    assert 'error' not in response
    assert not organization_monitor_healthy.watcher_list.users.exists()


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_bulk_watch_monitors(
    graphql_client, graphql_organization, organization_monitor_healthy
):
    response = graphql_client.execute(
        BULK_SUBSCRIPTION_TO_MANY_MONITORS,
        variables={
            'input': {'eventType': WATCH, 'ids': [organization_monitor_healthy.id]}
        },
    )
    organization_monitor_healthy.watcher_list.refresh_from_db()
    assert 'error' not in response
    assert organization_monitor_healthy.watcher_list.users.exists()


GET_ORDERED_ORGANIZATION_MONITORS = '''
        query organizationMonitors($orderBy: [OrderInputType]) {
          organizationMonitors(orderBy: $orderBy) {
            results {
              id
              isUserWatching
              watcherList {
                id
                watchers {
                  id
                  firstName
                  lastName
                }
              }
            }
          }
        }
    '''


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_organization_monitors_ordered_by_is_user_watching_desc(
    graphql_client,
    graphql_organization,
):
    organization_monitor_without_myself = create_organization_monitor(
        organization=graphql_organization
    )
    organization_monitor_with_myself = create_organization_monitor(
        organization=graphql_organization
    )
    user = graphql_client.context.get('user')
    organization_monitor_with_myself.watcher_list.users.add(user)
    response = graphql_client.execute(
        GET_ORDERED_ORGANIZATION_MONITORS,
        variables={'orderBy': [{'field': 'is_user_watching', 'order': 'descend'}]},
    )
    organization_monitors = response['data']['organizationMonitors']['results']
    organization_monitor_ids = [item['id'] for item in organization_monitors]
    expected = [
        str(organization_monitor_with_myself.id),
        str(organization_monitor_without_myself.id),
    ]
    assert organization_monitor_ids == expected


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
def test_get_organization_monitors_ordered_by_is_user_watching_asc(
    graphql_client,
    graphql_organization,
):
    organization_monitor_without_myself = create_organization_monitor(
        organization=graphql_organization
    )
    organization_monitor_with_myself = create_organization_monitor(
        organization=graphql_organization
    )
    user = graphql_client.context.get('user')
    organization_monitor_with_myself.watcher_list.users.add(user)
    response = graphql_client.execute(
        GET_ORDERED_ORGANIZATION_MONITORS,
        variables={'orderBy': [{'field': 'is_user_watching', 'order': 'ascend'}]},
    )
    organization_monitors = response['data']['organizationMonitors']['results']
    organization_monitor_ids = [item['id'] for item in organization_monitors]
    expected = [
        str(organization_monitor_without_myself.id),
        str(organization_monitor_with_myself.id),
    ]
    assert organization_monitor_ids == expected


# problems in resolve_events()
# contains lookup is not supported on this database backend
@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
@pytest.mark.skip()
def test_get_org_monitors_watched_by_user_without_organization_monitor(
    graphql_client,
    graphql_organization,
):
    user = graphql_client.context.get('user')
    organization_monitor_without_myself = create_organization_monitor(
        organization=graphql_organization
    )
    organization_monitor_without_myself.watcher_list.users.add(user)
    organization_monitor_without_myself.watcher_list = None
    organization_monitor_without_myself.save()
    create_organization_monitor(
        organization=graphql_organization
    ).watcher_list.users.add(user)
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    organization_monitors = response['data']['organizationMonitors']['results']
    assert 'errors' not in response
    assert len(organization_monitors) == 2


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
@pytest.mark.skip()
def test_get_organization_monitor_can_show_banner(
    graphql_client,
    graphql_organization,
):
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    events = response['data']['organizationMonitors']['events']
    assert events['showBanner']


@pytest.mark.functional(permissions=['monitor.view_monitor', 'user.view_user'])
@pytest.mark.skip()
def test_get_organization_monitor_can_not_show_banner(
    graphql_client,
    graphql_organization,
):
    user = graphql_client.context.get('user')
    MonitorSubscriptionEvent.objects.create(
        organization=graphql_organization,
        user=user,
        event_type=MonitorUserEventsOptions.CLOSE_DYNAMIC_BANNER,
    )
    response = graphql_client.execute(GET_ORGANIZATION_MONITORS)
    events = response['data']['organizationMonitors']['events']
    assert not events['showBanner']


@pytest.mark.functional
def test_heroku_configuration(graphql_organization):
    credentials = {"apiKey": encrypt_value("api_key_mock"), "email": "email_test"}
    connection_account = create_connection_account(
        'Heroku',
        configuration_state={'credentials': credentials},
        status=SUCCESS,
        organization=graphql_organization,
    )
    configuration = get_heroku_configuration("laika", connection_account)
    assert 'connection "laika" {' in configuration
    assert 'plugin    = "heroku"' in configuration
    assert 'api_key = "api_key_mock"' in configuration
    assert 'email   = "email_test"' in configuration


@pytest.mark.functional
def test_okta_configuration(graphql_organization):
    credentials = {"apiToken": "api_key_mock", "subdomain": "test-domain-admin"}
    connection_account = create_connection_account(
        'Okta',
        configuration_state={'credentials': credentials},
        status=SUCCESS,
        organization=graphql_organization,
    )
    configuration = get_okta_configuration("laika", connection_account)
    assert 'connection "laika" {' in configuration
    assert 'plugin    = "okta"' in configuration
    assert 'token = "api_key_mock"' in configuration
    assert 'domain   = "https://test-domain"' in configuration
