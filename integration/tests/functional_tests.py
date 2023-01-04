import datetime
import json
from unittest.mock import call, patch

import pytest
from django.test import RequestFactory
from reversion.models import Version

from access_review.evidence import reconcile_access_review_objects
from access_review.models import AccessReviewObject
from alert.constants import ALERT_TYPES_LAIKA_OBJECTS
from alert.models import Alert
from feature.models import Flag
from integration.constants import ERROR, PENDING, SUCCESS, SYNC
from integration.error_codes import (
    CONNECTION_TIMEOUT,
    DENIAL_OF_CONSENT,
    EXPIRED_TOKEN,
    INSUFFICIENT_PERMISSIONS,
    NONE,
    PROVIDER_SERVER_ERROR,
)
from integration.exceptions import ConfigurationError
from integration.google.tests.functional_tests import (
    google_workspace_connection_account,
)
from integration.models import ConnectionAccount
from integration.tasks import (
    run_connection_account_integration_for_access_review,
    run_vendor_integrations_per_organization,
    update_integrations,
)
from integration.views import oauth_callback
from objects.models import LaikaObject, LaikaObjectAlert
from objects.system_types import USER, resolve_laika_object_type
from objects.tests.factory import create_lo_with_connection_account
from objects.utils import create_background_check_alerts
from organization.models import ACTIVE
from organization.tests import create_organization
from user.constants import ROLE_ADMIN
from user.data_loaders import UserLoaders
from user.models import User
from user.tests import create_user
from vendor.tests.factory import create_vendor

from ..checkr.implementation import CHECKR_SYSTEM
from ..encryption_utils import encrypt_value
from ..factory import get_integration_name
from ..types import FieldOptionsResponseType
from .factory import create_connection_account, create_debug_status, create_integration

LAIKA_ALIAS = 'Laika Alias'

CONNECTION_TEST_ALIAS = 'connection test alias'
CONNECTION_TEST = 'connection test'


@pytest.mark.functional
def test_get_connection_account_status():
    integration = create_integration('testing')
    connection_account = create_connection_account(
        'testing',
        integration=integration,
    )
    assert connection_account.status == PENDING


@pytest.mark.functional
def test_update_integrations_ignore_pending_connections():
    google_workspace_connection_account(status=PENDING)
    updated = update_integrations()
    assert updated.get('executed_connections') == 0


def generate_testing_role(role_name: str):
    return {'Roles': [{'roleName': role_name}]}


@pytest.mark.functional
def test_access_review_object_modified(payload_for_access_review_tests):
    (
        laika_object,
        access_review_object,
        connection_account,
    ) = payload_for_access_review_tests
    laika_object.data = generate_testing_role('after update')
    laika_object.save()
    reconcile_access_review_objects(connection_account)
    access_review_object.refresh_from_db()
    assert (
        access_review_object.review_status == AccessReviewObject.ReviewStatus.MODIFIED
    )


@pytest.mark.functional
def test_access_review_object_revoked(payload_for_access_review_tests):
    (
        laika_object,
        access_review_object,
        connection_account,
    ) = payload_for_access_review_tests
    laika_object.deleted_at = datetime.datetime.now()
    laika_object.save()
    reconcile_access_review_objects(connection_account)
    access_review_object.refresh_from_db()
    assert access_review_object.review_status == AccessReviewObject.ReviewStatus.REVOKED


@pytest.mark.functional
def test_access_review_object_unchanged(payload_for_access_review_tests):
    access_review_object = payload_for_access_review_tests[1]
    connection_account = payload_for_access_review_tests[2]
    reconcile_access_review_objects(connection_account)
    access_review_object.refresh_from_db()
    assert (
        access_review_object.review_status == AccessReviewObject.ReviewStatus.UNCHANGED
    )


@pytest.mark.functional
def test_update_integrations_on_valid_and_invalid_statuses_to_execute():
    organization = create_organization(name='organization', state=ACTIVE)
    created_by = create_user(organization, email='heylaika@heylaika.com')

    # Not executed
    create_connection_account(
        'Bitbucket', status=PENDING, created_by=created_by, organization=organization
    )
    create_connection_account(
        'GCP', status=SYNC, created_by=created_by, organization=organization
    )
    create_connection_account(
        'Jamf',
        status=ERROR,
        error_code=EXPIRED_TOKEN,
        created_by=created_by,
        organization=organization,
    )

    # Executed
    connection_1 = create_connection_account(
        'Google Workspace',
        status=SUCCESS,
        created_by=created_by,
        organization=organization,
    )
    connection_2 = create_connection_account(
        'Github',
        status=ERROR,
        error_code=DENIAL_OF_CONSENT,
        created_by=created_by,
        organization=organization,
    )
    connection_3 = create_connection_account(
        'Asana',
        status=ERROR,
        error_code=CONNECTION_TIMEOUT,
        created_by=created_by,
        organization=organization,
    )
    connection_4 = create_connection_account(
        'Jira',
        status=ERROR,
        error_code=INSUFFICIENT_PERMISSIONS,
        created_by=created_by,
        organization=organization,
    )
    connection_5 = create_connection_account(
        'Datadog',
        status=ERROR,
        error_code=PROVIDER_SERVER_ERROR,
        created_by=created_by,
        organization=organization,
    )
    connection_6 = create_connection_account(
        'Sentry',
        status=ERROR,
        error_code=NONE,
        created_by=created_by,
        organization=organization,
    )

    with patch('integration.tasks.connection_within_interval') as interval_mck:
        with patch('integration.tasks.run_integration.delay') as delay_mck:
            interval_mck.return_value = True
            execution_result = update_integrations()
            delay_mck.assert_has_calls(
                [
                    call(connection_id=connection_1.id, send_mail_error=True),
                    call(connection_id=connection_2.id, send_mail_error=True),
                    call(connection_id=connection_3.id, send_mail_error=True),
                    call(connection_id=connection_4.id, send_mail_error=True),
                    call(connection_id=connection_5.id, send_mail_error=False),
                    call(connection_id=connection_6.id, send_mail_error=True),
                ],
            )

    assert execution_result.get('executed_connections') == 6


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_dataloaders_created_by_value_order(graphql_organization):
    loaders = UserLoaders()
    create_user(graphql_organization, [], 'test1@heylaika.com')
    create_user(graphql_organization, [], 'test2@heylaika.com')
    create_user(graphql_organization, [], 'test3@heylaika.com')
    users = User.objects.all()
    user_ids = [user.id for user in users]
    user_ids.reverse()
    user_loader = loaders.users_by_id.load_many(user_ids)
    loader_keys = [user.id for user in user_loader.value]
    assert loader_keys == user_ids


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_integrations_query_with_empty_connections(graphql_client):
    vendor_name = 'testing'
    create_integration(vendor_name)

    response = graphql_client.execute(GET_INTEGRATIONS_QUERY)

    integration = response['data']['integrations'][0]
    assert integration['vendor']['name'] == vendor_name
    assert integration['category'] == 'other'
    assert integration['connectionAccounts'] == []


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_integrations_query_with_connections(
    graphql_client, graphql_organization
):
    connection_account = create_connection_account(
        'testing', alias='testing_connection', organization=graphql_organization
    )

    response = graphql_client.execute(GET_INTEGRATIONS_QUERY)

    response_integration = response['data']['integrations'][0]
    response_connection_account = response_integration['connectionAccounts'][0]
    assert response_connection_account['id'] == str(connection_account.id)
    assert response_connection_account['status'] == connection_account.status


@pytest.mark.functional(permissions=['integration.add_connectionaccount'])
def test_graphql_mutation_start_integration(graphql_client):
    vendor_name = CONNECTION_TEST
    alias = CONNECTION_TEST_ALIAS
    create_integration(vendor_name)
    params = {'vendorName': vendor_name, 'alias': alias, 'subscriptionType': ''}

    response = graphql_client.execute(GET_START_INTEGRATION_QUERY, variables=params)[
        'data'
    ]['startIntegration']['connectionAccount']

    control = response['control']
    connection_account = ConnectionAccount.objects.filter(control=control)
    assert control is not None
    assert connection_account.exists()
    connection = connection_account.first()
    versions = Version.objects.get_for_object(connection)
    assert versions[0].revision.comment == 'Connection account created.'


@pytest.mark.functional(permissions=['integration.add_connectionaccount'])
def test_graphql_mutation_start_integration_non_duplicated_alias(graphql_client):
    vendor_name = CONNECTION_TEST
    alias = CONNECTION_TEST_ALIAS
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name,
        alias=alias,
        integration=integration,
    )
    params = {'vendorName': vendor_name, 'alias': alias, 'subscriptionType': None}

    with pytest.raises(Exception):
        create_connection_account(
            vendor_name,
            alias=alias,
            integration=integration,
        )
        graphql_client.execute(GET_START_INTEGRATION_QUERY, variables=params)


@pytest.mark.functional(permissions=['integration.add_connectionaccount'])
def test_graphql_mutation_start_integration_non_duplicated_alias_with_spaces(
    graphql_client,
):
    vendor_name = CONNECTION_TEST
    alias = CONNECTION_TEST_ALIAS
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name,
        alias=alias,
        integration=integration,
    )
    params = {'vendorName': vendor_name, 'alias': alias}

    with pytest.raises(Exception):
        create_connection_account(
            vendor_name,
            alias=' connection       test    alias          ',
            integration=integration,
        )
        graphql_client.execute(GET_START_INTEGRATION_QUERY, variables=params)


@pytest.mark.functional
def test_configuration_error_set_error_code():
    connection_account = create_connection_account(
        'jira', alias='Connection Account Testing'
    )
    request = RequestFactory().get('/', {'state': connection_account.control})
    with patch('integration.views.get_connection_from_state') as mck:
        mck.return_value = connection_account
        oauth_callback(request, 'jira')
    connection_account = ConnectionAccount.objects.get(control=request.GET.get('state'))
    assert connection_account.error_code == DENIAL_OF_CONSENT
    versions = Version.objects.get_for_object(connection_account)
    assert (
        versions[0].revision.comment
        == 'OAuth callback executed and ended on pending status.'
    )


@pytest.mark.functional
def test_configuration_error_denial_consent_error():
    connection_account = create_connection_account(
        'github', alias='Connection Account Testing'
    )
    request = RequestFactory().get('/', {'state': connection_account.control})
    with patch('integration.views.get_connection_from_state') as mck:
        mck.return_value = connection_account
        oauth_callback(request, 'github')
    connection_account = ConnectionAccount.objects.get(control=request.GET.get('state'))
    assert connection_account.error_code == DENIAL_OF_CONSENT


@pytest.mark.functional(permissions=['integration.change_connectionaccount'])
def test_update_connection_account(graphql_client, graphql_organization):
    connection_account = create_connection_account(
        'testing',
        alias='testing_connection',
        organization=graphql_organization,
        authentication={},
    )
    with patch(
        'integration.models.ConnectionAccount.bulk_update_objects_connection_name'
    ) as update_mock:
        resp = graphql_client.execute(
            UPDATE_CONNECTION_ACCOUNT,
            variables={'id': connection_account.id, 'alias': 'updated alias'},
        )
        update_mock.assert_called_once()

    updated_conn = resp['data']['updateConnectionAccount']['connectionAccount']
    expected = dict(
        id=str(connection_account.id),
        alias='updated alias',
        status='pending',
        configurationState='{}',
        errorMessage='',
    )

    assert updated_conn == expected


@pytest.mark.functional(permissions=['integration.change_connectionaccount'])
def test_update_connection_account_without_alias(graphql_client, graphql_organization):
    connection_account = create_connection_account(
        'testing',
        alias='testing_connection',
        organization=graphql_organization,
        authentication={},
    )
    resp = graphql_client.execute(
        UPDATE_CONNECTION_ACCOUNT,
        variables={
            'id': connection_account.id,
            'configurationState': '{"test": "updated"}',
        },
    )
    updated_conn = resp['data']['updateConnectionAccount']['connectionAccount']
    expected = dict(
        id=str(connection_account.id),
        alias='testing_connection',
        status='pending',
        configurationState='{"test": "updated"}',
        errorMessage='',
    )

    assert updated_conn == expected


@pytest.mark.functional(permissions=['integration.change_connectionaccount'])
def test_update_connection_account_with_client_credentials(
    graphql_client, graphql_organization
):
    connection_account = create_connection_account(
        'datadog',
        alias='datadog_test_connection',
        organization=graphql_organization,
        authentication={},
    )
    configuration_state = {
        'credentials': {
            'apiKey': encrypt_value('api_key'),
            'programKey': encrypt_value('program_key'),
        }
    }
    resp = graphql_client.execute(
        UPDATE_CONNECTION_ACCOUNT,
        variables={
            'id': connection_account.id,
            'configurationState': json.dumps(configuration_state),
        },
    )
    updated_conn = resp['data']['updateConnectionAccount']['connectionAccount']
    credentials_got = json.loads(updated_conn['configurationState'])['credentials']
    assert credentials_got == configuration_state['credentials']
    assert 'error' == updated_conn['status']


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_get_integration_by_vendor_name(graphql_client):
    vendor_name = 'google_workspace_test'
    create_integration(vendor_name)
    args = {'name': vendor_name}

    response = graphql_client.execute(GET_INTEGRATION_BY_NAME_QUERY, variables=args)
    integration = response['data']['integration']
    assert integration is not None
    assert integration['vendor']['name'] == vendor_name
    assert 'permissions' in integration


@pytest.mark.functional(permissions=['integration.view_connectionaccount'])
def test_graphql_get_custom_field_options(graphql_client, graphql_organization):
    connection_account = google_workspace_connection_account(
        status=SUCCESS, organization=graphql_organization
    )
    test_field_name = 'test_field'

    def get_custom_field_options_dummy(field_name, wizard_state):
        return FieldOptionsResponseType(
            options=[{'id': 'TR', 'value': {'name': 'Transformers'}}]
        )

    from integration import google

    google.get_custom_field_options = get_custom_field_options_dummy
    params = {
        'connection_id': connection_account.id,
        'field_name': test_field_name,
    }

    response = graphql_client.execute(GET_LOAD_FIELD_VALUES, variables=params)['data'][
        'getCustomFieldOptions'
    ]

    option, *_ = response['options']
    expected_option = {'id': 'TR', 'value': '{"name": "Transformers"}'}
    assert response['total'] == 1
    assert option == expected_option


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_object_connection_account_query(graphql_client, graphql_organization):
    lo_type = resolve_laika_object_type_with_elements(graphql_organization, USER)
    response = graphql_client.execute(
        GET_CONNECTION_ACCOUNT_BY_LAIKA_OBJECT,
        variables={'objectId': '1', 'objectTypeName': lo_type.type_name},
    )

    connection_account = response['data']['objectConnectionAccount']
    assert connection_account is not None
    assert connection_account['integration']['description'] == 'Dummy Integration'
    assert connection_account['status'] == PENDING


def resolve_laika_object_type_with_elements(organization, spec):
    laika_type = resolve_laika_object_type(organization, spec)
    if laika_type:
        laika_object = {
            'object_type': laika_type,
            'is_manually_created': True,
            'data': dict(
                first_name='Laika', last_name='Organization', email='laika@laika.com'
            ),
            'connection_account': create_connection_account(
                'testing', alias='testing_connection', organization=organization
            ),
        }
        LaikaObject.objects.create(**laika_object)
    return laika_type


@pytest.mark.functional(permissions=['integration.delete_connectionaccount'])
def test_delete_connection_account(graphql_client, graphql_organization):
    connection_account = create_connection_account(
        'testing-to-delete',
        alias='testing_deleted_connection',
        organization=graphql_organization,
        authentication={},
    )
    resp = graphql_client.execute(
        DELETE_CONNECTION_ACCOUNT, variables={'id': connection_account.id}
    )
    deleted_resp = resp['data']['deleteConnectionAccount']
    deleted_conn = deleted_resp['connectionAccount']['alias']

    assert deleted_conn == 'testing_deleted_connection'


@pytest.mark.functional(permissions=['integration.delete_connectionaccount'])
def test_delete_checkr_connection_account_with_lo_and_alerts_associated(
    graphql_client, graphql_organization
):
    laika_objects, connection_account = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data=[
            {'First Name': 'Leo', 'Last Name': 'Messi', 'Link to People Table': None},
            {
                'First Name': 'cristiano',
                'Last Name': 'ronaldo',
                'Link to People Table': None,
            },
        ],
    )
    create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )
    create_background_check_alerts(
        alert_related_object={'laika_object': laika_objects[0]},
        alert_related_model='objects.LaikaObjectAlert',
        alert_type=ALERT_TYPES_LAIKA_OBJECTS.get(
            'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER', ''
        ),
        organization_id=graphql_organization.id,
    )
    response = graphql_client.execute(
        DELETE_CONNECTION_ACCOUNT, variables={'id': connection_account.id}
    )
    assert ConnectionAccount.objects.filter(id=connection_account.id).exists() is False
    assert (
        LaikaObjectAlert.objects.filter(laika_object__id=laika_objects[0].id).count()
        == 0
    )
    assert (
        LaikaObject.objects.filter(
            id__in=[laika_objects[0].id, laika_objects[1].id]
        ).count()
        == 0
    )
    assert Alert.objects.all().count() == 0
    assert (
        response['data']['deleteConnectionAccount']['connectionAccount']['alias']
        == 'checkr test'
    )


@pytest.mark.functional(permissions=['integration.delete_connectionaccount'])
def test_delete_connection_account_syncing(graphql_client, graphql_organization):
    connection_account = create_connection_account(
        'testing-to-delete',
        alias='testing_deleted_connection',
        organization=graphql_organization,
        authentication={},
    )
    connection_account.status = 'sync'
    connection_account.save()
    resp = graphql_client.execute(
        DELETE_CONNECTION_ACCOUNT, variables={'id': connection_account.id}
    )
    error_message = resp['errors'][0]['message']
    assert error_message == 'Failed to delete connection account'


@pytest.mark.functional(permissions=['integration.change_connectionaccount'])
def test_update_connection_account_with_exception(graphql_client, graphql_organization):
    connection_account = create_connection_account(
        'datadog',
        alias='testing_connection_exception',
        organization=graphql_organization,
        authentication={},
    )
    configuration_state = {
        'credentials': {'apiKey': 'api_key', 'programKey': 'program_key'}
    }
    with patch('integration.factory.get_integration') as mock:
        mock.return_value = ErrorImplementation()
        graphql_client.execute(
            UPDATE_CONNECTION_ACCOUNT,
            variables={
                'id': connection_account.id,
                'configurationState': json.dumps(configuration_state),
            },
        )
    connection_account.refresh_from_db()
    assert connection_account.status == 'error'


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_cloud_providers_feature_flag_disabled(graphql_client, graphql_organization):
    Flag.objects.update_or_create(
        name='awsIntegrationFeatureFlag',
        organization_id=graphql_organization.id,
        is_enabled=False,
    )
    vendor_name = 'AWS'
    create_integration(vendor_name)
    vendor_name = 'Github'
    create_integration(vendor_name)
    response = graphql_client.execute(GET_INTEGRATIONS_QUERY)
    response_integration = response['data']['integrations']

    assert len(response_integration) == 2


@pytest.mark.functional(permissions=['integration.add_connectionaccount'])
def test_graphql_mutation_start_integration_with_duplicate_alias(
    graphql_client, graphql_organization
):
    vendor_name = CONNECTION_TEST
    alias = LAIKA_ALIAS
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name=vendor_name,
        alias=alias,
        integration=integration,
        organization=graphql_organization,
    )

    params = {'vendorName': vendor_name, 'alias': alias, 'subscriptionType': ''}

    result = graphql_client.execute(GET_START_INTEGRATION_QUERY, variables=params)
    assert result['errors'][0]['message'] == 'Connection already exists'


@pytest.mark.functional(permissions=['integration.add_connectionaccount'])
def test_graphql_query_get_connection_account_checkr_authorized(
    graphql_client, graphql_organization
):
    vendor_name = 'checkr'
    alias = LAIKA_ALIAS
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name=vendor_name,
        alias=alias,
        integration=integration,
        organization=graphql_organization,
        authentication={'authorized': True},
        error_code='016',
    )

    params = {
        'vendorName': vendor_name,
    }

    result = graphql_client.execute(CONNECTION_ACCOUNT_BY_VENDOR, variables=params)
    response = result['data']['connectionAccount']
    assert json.loads(response['authenticationMetadata'])['authorized'] is True


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_mutation_checkr_operation_without_connection_account(
    graphql_client, graphql_organization
):
    result = graphql_client.execute(
        EXECUTE_INTEGRATION_API,
        variables={'endpoint': 'account_details', 'vendor': CHECKR_SYSTEM},
    )
    assert result['data']['executeIntegrationApi'] is None


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_mutation_checkr_operation_without_token(
    graphql_client, graphql_organization
):
    vendor_name = CHECKR_SYSTEM
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name=vendor_name,
        alias=LAIKA_ALIAS,
        integration=integration,
        organization=graphql_organization,
    )
    result = graphql_client.execute(
        EXECUTE_INTEGRATION_API,
        variables={'endpoint': 'account_details', 'vendor': CHECKR_SYSTEM},
    )
    assert (
        result['errors'][0]['message'] == 'The connection account does not have token'
    )


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_mutation_checkr_operation_wrong_endpoint_name(
    graphql_client, graphql_organization
):
    vendor_name = CHECKR_SYSTEM
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name=vendor_name,
        alias=LAIKA_ALIAS,
        integration=integration,
        organization=graphql_organization,
    )
    result = graphql_client.execute(
        EXECUTE_INTEGRATION_API,
        variables={'endpoint': 'wrong_endpoint', 'vendor': CHECKR_SYSTEM},
    )
    assert result['errors'][0]['message'] == 'The endpoint is not valid'


@pytest.mark.functional(permissions=['integration.view_integration'])
@patch('integration.checkr.execute_api.getattr')
def test_graphql_mutation_execute_integration_checkr_account_details(
    get_account_details_mock, graphql_client, graphql_organization
):
    email = "ross.loney@heylaika.com"

    def _get_account_details_mock(**kwargs):
        return {
            "adverse_action_email": email,
            "api_authorized": False,
            "authorized": False,
        }

    vendor_name = CHECKR_SYSTEM
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name=vendor_name,
        alias=LAIKA_ALIAS,
        integration=integration,
        organization=graphql_organization,
        authentication={"access_token": "acd8b7d91fbb9edce2228e3064c7f7ad9519cde9"},
    )
    get_account_details_mock.return_value = _get_account_details_mock
    result = graphql_client.execute(
        EXECUTE_INTEGRATION_API,
        variables={'endpoint': 'account_details', 'vendor': vendor_name},
    )
    response = json.loads(result['data']['executeIntegrationApi']['response'])
    assert response['adverse_action_email'] == email
    assert response['authorized'] is False


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_mutation_execute_integration_checkr_create_candidate(
    graphql_client, graphql_organization
):
    candidate_id = "0c99cdf88a2e3468b7732646"
    email = "ross.loney@heylaika.com"
    package = "laika_driver_standard"

    def _create_candidate_mock():
        return {
            "id": candidate_id,
            "email": email,
            "first_name": None,
        }

    def _send_invitation_mock():
        return {
            "id": "ce97340b9b5927e63207b3ea",
            "status": "pending",
            "candidate_id": candidate_id,
            "package": package,
        }

    vendor_name = CHECKR_SYSTEM
    integration = create_integration(vendor_name)
    create_connection_account(
        vendor_name=vendor_name,
        alias=LAIKA_ALIAS,
        integration=integration,
        organization=graphql_organization,
        authentication={"access_token": "acd8b7d91fbb9edce2228e3064c7f7ad9519cde9"},
    )
    with patch(
        'integration.checkr.rest_client.create_candidates'
    ) as create_candidates_mock:
        with patch(
            'integration.checkr.rest_client.send_invitation'
        ) as send_invitation_mock:
            create_candidates_mock.return_value = _create_candidate_mock()
            send_invitation_mock.return_value = _send_invitation_mock()
            result = graphql_client.execute(
                EXECUTE_INTEGRATION_API,
                variables={
                    'endpoint': 'create_candidates',
                    'vendor': vendor_name,
                    'data': json.dumps(
                        {
                            "email": email,
                            "packages": package,
                            "work_locations": [{"state": "AL", "city": "Birmingham"}],
                        }
                    ),
                },
            )
            response = json.loads(result['data']['executeIntegrationApi']['response'])
            assert response['candidate_id'] == candidate_id
            assert response['package'] == package
            assert response['status'] == 'pending'
            create_candidates_mock.assert_called_once()
            send_invitation_mock.assert_called_once()
            assert (
                LaikaObject.objects.filter(
                    object_type__type_name='background_check'
                ).count()
                == 1
            )


@pytest.mark.functional(permissions=['integration.change_connectionaccount'])
def test_update_connection_account_with_latest_version(
    graphql_client, graphql_organization
):
    vendor_name = 'testing'
    connection_account = create_connection_account(
        vendor_name=vendor_name,
        alias='testing_connection',
        organization=graphql_organization,
        configuration_state=dict(settings="test-settings"),
    )
    integration = connection_account.integration
    new_version = integration.versions.create(
        version_number='2.0.0', metadata=dict(permissions=dict(type='Read only'))
    )
    resp = graphql_client.execute(
        UPDATE_CONNECTION_ACCOUNT,
        variables={
            'id': connection_account.id,
            'configurationState': "{\"settings\":\"test-settings\"}",
            'completed': True,
        },
    )

    updated_connection_id = resp['data']['updateConnectionAccount'][
        'connectionAccount'
    ]['id']
    updated_connection = ConnectionAccount.objects.get(id=updated_connection_id)
    assert updated_connection.integration_version == new_version


@pytest.mark.functional
@pytest.mark.parametrize('vendor_name', ['jira', 'datadog'])
def test_run_optimized_vendors(vendor_name):
    connection_account = create_connection_account(vendor_name)
    with (patch(f'integration.{vendor_name}') as integration,):
        run_connection_account_integration_for_access_review(connection_account)
        assert integration.run_by_lo_types.called


@pytest.mark.functional
@pytest.mark.parametrize('vendor_name', ['gitlab', 'heroku'])
def test_run_non_optimized_vendors(vendor_name):
    connection_account = create_connection_account(vendor_name)
    with (patch(f'integration.{vendor_name}') as integration,):
        run_connection_account_integration_for_access_review(connection_account)
        assert integration.run.called


class ErrorImplementation:
    def connect(self, connection_account):
        raise ValueError('Simulating connection error')


def mock_run_integration(connection_account: ConnectionAccount):
    if 'error' in connection_account.alias:
        raise ValueError('Simulating error from an integration run')
    connection_account.status = SUCCESS
    connection_account.save()


@pytest.fixture
def vendor_for_ar():
    return create_vendor('github apps')


@pytest.fixture
def success_connection_account_for_ar(
    vendor_for_ar, graphql_organization, graphql_user
):
    create_connection_account(
        vendor_for_ar.name,
        alias='success',
        created_by=graphql_user,
        organization=graphql_organization,
        vendor=vendor_for_ar,
    )


@pytest.fixture
def error_connection_account_for_ar(vendor_for_ar, graphql_organization, graphql_user):
    create_connection_account(
        vendor_for_ar.name,
        alias='error',
        created_by=graphql_user,
        organization=graphql_organization,
        vendor=vendor_for_ar,
    )


RUN_INTEGRATION_FOR_AR_PATH = (
    'integration.tasks.run_connection_account_integration_for_access_review'
)


@pytest.mark.django_db
def test_run_vendor_integration_per_org_success(
    graphql_organization, vendor_for_ar, success_connection_account_for_ar
):
    with patch(RUN_INTEGRATION_FOR_AR_PATH, side_effect=mock_run_integration):
        assert run_vendor_integrations_per_organization(
            graphql_organization.id, vendor_for_ar.id
        )['success']


@pytest.mark.functional
def test_run_vendor_integration_per_org_error_handling(
    graphql_organization,
    vendor_for_ar,
    success_connection_account_for_ar,
    error_connection_account_for_ar,
):
    with patch(RUN_INTEGRATION_FOR_AR_PATH, side_effect=mock_run_integration):
        assert run_vendor_integrations_per_organization(
            graphql_organization.id, vendor_for_ar.id
        )['success']


@pytest.mark.functional
def test_run_vendor_integration_per_org_fail(
    graphql_organization, vendor_for_ar, error_connection_account_for_ar
):
    with patch(
        RUN_INTEGRATION_FOR_AR_PATH, side_effect=mock_run_integration
    ), pytest.raises(ConfigurationError):
        run_vendor_integrations_per_organization(
            graphql_organization.id, vendor_for_ar.id
        )


@pytest.mark.parametrize(
    'integration_key,expected_name',
    [('aws', 'AWS'), ('microsoft_azure', 'Microsoft Azure')],
)
def test_get_integration_names(integration_key, expected_name):
    name = get_integration_name(integration_key)

    assert name == expected_name


@pytest.mark.functional(permissions=['integration.view_integration'])
def test_graphql_get_debug_status(graphql_organization, graphql_client):
    vendor_name = 'Jira Integration'
    integration = create_integration(vendor_name)
    connection_account = create_connection_account(
        vendor_name=vendor_name,
        integration=integration,
        organization=graphql_organization,
    )
    connection_account.debug_status = create_debug_status()
    connection_account.save()
    args = {'name': vendor_name}

    response = graphql_client.execute(GET_INTEGRATION_BY_NAME_QUERY, variables=args)
    connection_account_response = response['data']['integration']['connectionAccounts'][
        0
    ]
    debug_status = connection_account_response['debugStatus']
    assert connection_account_response is not None
    assert debug_status['status'] == 'LAIKA_ACTION_REQUIRED'


GET_INTEGRATIONS_QUERY = '''
    query getIntegrations {
        integrations {
            id
            vendor {
                name
                logo {
                    url
                }
            }
            description
            category
            metadata {
                key
                value
            }
            connectionAccounts {
                id
                status
            }
        }
    }
    '''
GET_START_INTEGRATION_QUERY = '''
    mutation($vendorName: String!, $alias: String!,
       $subscriptionType: String!) {
       startIntegration(vendorName: $vendorName,
       alias: $alias, subscriptionType: $subscriptionType) {
         connectionAccount {
          control
          alias
      }
    }
  }
'''

GET_INTEGRATION_BY_NAME_QUERY = '''
    query getIntegrationByName($name: String) {
        integration(name: $name) {
            id
            vendor {
                name
                logo {
                    url
                }
                fullLogo {
                    url
                }
            }
            description
            metadata {
                key
                value
            }
            requirements
            connectionAccounts {
                id
                alias
                status
                control
                createdAt
                createdBy {
                    firstName
                    lastName
                }
                configurationState
                errorCodeMessage
                debugStatus {
                    status
                    name
                }
            }
            permissions
        }
    }
    '''

UPDATE_CONNECTION_ACCOUNT = '''
    mutation($id: Int!, $configurationState: JSONString,
        $alias: String, $completed: Boolean) {
        updateConnectionAccount(
         id: $id,
         alias: $alias,
         completed: $completed,
         configurationState: $configurationState
         )
         {
            connectionAccount {
                id
                alias
                configurationState
                status
                errorMessage
            }
        }
    }
    '''

GET_LOAD_FIELD_VALUES = '''
    query getCustomFieldOptions(
            $connection_id:Int!,
            $field_name:String!
        ){
        getCustomFieldOptions
        (
            connectionId:$connection_id,
            fieldName:$field_name
        ) {
            total
            options{
                id
                value
            }
    }
}
    '''

GET_CONNECTION_ACCOUNT_BY_LAIKA_OBJECT = '''
query objectConnectionAccount(
    $objectTypeName: String!
    $objectId: Int!
  ) {
    objectConnectionAccount(
        objectTypeName: $objectTypeName,
        objectId: $objectId
    ){
        id
        status
        configurationState
        integration {
          description
          vendor {
            logo {
              url
            }
          }
        }
    }
  }
'''

DELETE_CONNECTION_ACCOUNT = '''
    mutation($id: Int!) {
        deleteConnectionAccount(id: $id) {
          connectionAccount {
            alias
          }
        }
      }
    '''


EXECUTE_INTEGRATION_API = '''
    mutation ExecuteIntegrationApi($endpoint: String!, $vendor: String!,
    $data: JSONString) {
        executeIntegrationApi(endpoint: $endpoint, vendor: $vendor, data: $data
        ) {
            response
        }
    }
    '''


CONNECTION_ACCOUNT_BY_VENDOR = '''
    query getConnectionAccount($control: String, $vendorName: String){
        connectionAccount(control: $control, vendorName: $vendorName) {
            id
            status
            integration {
                id
                description
                vendor {
                    id
                    name
                }
            }
            authenticationMetadata
            errorCodeMessage
        }
    }
    '''
