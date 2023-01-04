import os
import uuid
from datetime import datetime

import pytest
from django.core.files import File
from pytest import raises

from address.models import Address
from feature.constants import AUDITS_FEATURE_FLAG
from feature.tests.functional_tests import default_feature_flags_len
from integration.tests import create_connection_account
from organization.constants import ARCHITECT_MEETING, QUESTIONNAIRE
from organization.models import (
    ONBOARDING_SETUP_STEP,
    ApiTokenHistory,
    CheckIn,
    Onboarding,
    Organization,
    OrganizationLocation,
    handle_review_ready,
)
from organization.tasks import (
    attach_default_report_template,
    create_organization_drive,
    delete_organization_data,
    seed_base_profile,
    set_default_flags,
)
from organization.tests import create_organization
from organization.tests.mutations import (
    COMPLETE_ONBOARDING,
    CREATE_API_TOKEN,
    MOVE_ORG_OUT_OF_ONBOARDING,
    UPDATE_ONBOARDING_V2_STATE,
)
from organization.tests.queries import DELETE_API_TOKEN, GET_API_TOKENS
from organization.tests.test_utils import create_test_group
from seeder.constants import DONE
from seeder.models import Seed, SeedProfile
from user.constants import CONCIERGE_ROLES
from user.models import User
from user.tests import create_user

TEST_ORG = 'Test Org'
SEED_FILE_PATH = f'{os.path.dirname(__file__)}/resources/template_seed.zip'
FAKE_CALENDLY_URL = 'https://calendly.com/ca-user/test'

GET_ORGANIZATIONS_LIST_QUERY = '''
        query getAllOrganizations(
            $pagination: PaginationInputType
            $filter: [OrganizationFilterType]
            $searchCriteria: String
        ) {
            getAllOrganizations(
            pagination: $pagination
            filter: $filter
            searchCriteria: $searchCriteria
            ) {
            data {
                id
                name
                createdAt
                customerSuccessManagerUser {
                firstName
                lastName
                }
                complianceArchitectUser {
                firstName
                lastName
                }
                website
            }
            pagination {
                page
                current
                pages
                hasNext
                hasPrev
                pageSize
                total
            }
            }
        }
    '''


@pytest.fixture
def user_test(graphql_organization):
    return create_user(
        graphql_organization,
        email='luis@heylaika.com',
        role=CONCIERGE_ROLES.get('CONCIERGE'),
        first_name='Luis',
    )


FAKE_DATE = '2021-07-23'
FAKE_NOTE = 'Fake note 1'
FAKE_PARTICIPANT = 'Fake participant 1'
FAKE_ACTION_ITEM = 'Fake action item 1'


@pytest.fixture
def create_check_ins(graphql_organization, user_test):
    CheckIn.objects.create(
        organization=graphql_organization,
        cx_participant=user_test,
        date=FAKE_DATE,
        customer_participant=FAKE_PARTICIPANT,
        notes=FAKE_NOTE,
        action_items=FAKE_ACTION_ITEM,
    )


@pytest.fixture
def addresses(graphql_organization):
    us_address = Address.objects.create(
        street1='headquarters nyc', street2='apt 1', country='USA'
    )
    cr_address = Address.objects.create(
        street1='CR office', street2='apt 1 cr', country='CR'
    )
    OrganizationLocation.objects.create(
        organization=graphql_organization, address=us_address, hq=True
    )
    OrganizationLocation.objects.create(
        organization=graphql_organization, address=cr_address
    )
    return [us_address, cr_address]


def _get_organizations_list(response):
    return response['data']['getAllOrganizations']


def _get_filtered_organizations_list(response):
    return response['data']['getAllOrganizations']


def _get_filtered_organizations_by_name_list(response):
    return response['data']['getAllOrganizations']


def create_organization_with_list(org_name, user):
    return Organization.objects.create(
        name=org_name,
        website='https://orgone.com',
        customer_success_manager_user=user,
        compliance_architect_user=user,
    )


@pytest.fixture
def organizations_list():
    user = User.objects.create(
        first_name='John', last_name='Doe', email='sender@heylaika.com'
    )

    return [
        create_organization_with_list('Org 1', user),
        create_organization_with_list('Org 2', user),
        create_organization_with_list('Org 3', user),
    ]


@pytest.fixture
def organizations_list_by_name():
    user = User.objects.create(
        first_name='John', last_name='Doe', email='sender@heylaika.com'
    )

    return [
        create_organization_with_list('Searchable Organization', user),
        create_organization_with_list('Test Organization', user),
        create_organization_with_list('BB Organization', user),
    ]


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_organizations_list(graphql_client, organizations_list):
    executed = graphql_client.execute(
        GET_ORGANIZATIONS_LIST_QUERY,
        variables={'pagination': dict(page=1, pageSize=10)},
    )

    response = _get_organizations_list(executed)
    organization_response = response['data']

    row = 0
    for org in reversed(organizations_list):
        assert organization_response[row]['name'] == org.name
        assert organization_response[row]['website'] == org.website
        row += 1


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_filtered_organizations_list(graphql_client, organizations_list):
    executed = graphql_client.execute(
        GET_ORGANIZATIONS_LIST_QUERY,
        variables={
            'pagination': dict(page=1, pageSize=10),
            'filter': [
                {
                    'field': 'name',
                    'value': 'org',
                    'operator': 'contains',
                    'type': 'TEXT',
                },
                {
                    'field': 'customerSuccessManagerUser',
                    'value': '',
                    'operator': 'is_not_empty',
                    'type': 'USER',
                },
                {
                    'field': 'createdAt',
                    'value': '',
                    'operator': 'is_not_empty',
                    'type': 'DATE',
                },
            ],
        },
    )

    response = _get_filtered_organizations_list(executed)
    organization_response = response['data']

    row = 0
    for org in reversed(organizations_list):
        assert organization_response[row]['name'] == org.name
        row += 1


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_filtered_by_name_organizations_list(
    graphql_client, organizations_list_by_name
):
    executed = graphql_client.execute(
        GET_ORGANIZATIONS_LIST_QUERY,
        variables={'pagination': dict(page=1, pageSize=10), 'searchCriteria': 'search'},
    )

    response = _get_filtered_organizations_by_name_list(executed)
    organization_response = response['data']
    assert organization_response[0]['name'] == 'Searchable Organization'
    assert len(organization_response) == 1


@pytest.mark.functional(permissions=['organization.add_organization'])
def test_create_organization(graphql_client, user_test):
    user = {'firstName': 'Luis', 'lastName': 'Barrantes', 'email': 'luis@heylaika.com'}
    executed = graphql_client.execute(
        '''
        mutation createNewOrganization($input: OrganizationInput!) {
            createOrganization(input: $input) {
                success
                error {
                    code
                    message
                }
                organization {
                    id
                    name
                }
            }
        }
        ''',
        variables={
            'input': dict(
                name='Patito Inc',
                website='https://patito.com',
                customerSuccessManager=user,
                complianceArchitect=user,
            )
        },
    )

    response = executed['data']['createOrganization']
    assert response is not None
    assert response['success'] is True
    assert response['organization']['name'] == 'Patito Inc'


@pytest.mark.functional(permissions=['organization.change_organization'])
def test_organization_update_logo(graphql_client, graphql_organization):
    executed = graphql_client.execute(
        '''
        mutation updateOrganizationDetails($input: OrganizationInput!) {
            updateOrganization(input: $input) {
                success
                data {
                    name
                    website
                    description
                    logo
                    productOrServiceDescription
                }
                error {
                    code
                    message
                }
            }
        }
        ''',
        variables={
            'input': dict(
                name=graphql_organization.name,
                website=graphql_organization.website,
                fileName='file.jpg',
                fileContents='SG9sYSBteSB0ZXh0',
            )
        },
    )

    response = executed['data']['updateOrganization']
    assert response is not None
    assert response['success'] is True
    assert response['data']['name'] == graphql_organization.name
    assert response['data']['logo'] is not None


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_organization_by_id(graphql_client, graphql_organization):
    executed = graphql_client.execute(
        '''
        query Organization($id: String!) {
            organization: getOrganizationById(id: $id) {
                data {
                    id
                    name
                }
            }
        }

        ''',
        variables={'id': graphql_organization.id},
    )
    response = executed['data']['organization']['data']
    assert response['name'] == ''
    assert response['id'] == str(graphql_organization.id)


@pytest.mark.functional(permissions=['organization.view_organizationlocation'])
def test_get_organization_location(graphql_client, graphql_organization, addresses):
    response = graphql_client.execute(
        '''
        query getOrganization {
            getOrganization {
                data {
                    locations {
                        street1
                        street2
                        country
                    }
                }
            }
        }
        '''
    )['data']['getOrganization']['data']

    us_address, cr_address = addresses
    expected = [
        dict(
            street1=us_address.street1,
            street2=us_address.street2,
            country=us_address.country,
        ),
        dict(
            street1=cr_address.street1,
            street2=cr_address.street2,
            country=cr_address.country,
        ),
    ]
    assert response['locations'] == expected


@pytest.mark.functional(permissions=['organization.delete_organizationlocation'])
def test_update_hq_when_delete_current_hq(
    graphql_client, graphql_organization, addresses
):
    us_address, cr_address = addresses
    graphql_client.execute(
        '''
        mutation deleteLocation($input: [Int]!) {
            deleteLocation(input: $input) {
                deleted
            }
        }
        ''',
        variables={'input': [us_address.id]},
    )

    hq = OrganizationLocation.objects.filter(
        organization=graphql_organization, hq=True
    ).first()
    assert hq.id == cr_address.id


@pytest.mark.functional(permissions=['organization.change_onboarding'])
def test_update_onboarding_status(graphql_client, graphql_onboarding):
    graphql_client.execute(
        '''
        mutation updateOnboardingDetails($input: UpdateOnboardingInput!) {
            updateOnboarding(input: $input) {
                id
                state
            }
        }
        ''',
        variables={'input': {'state': 'REVIEW'}},
    )

    onboarding = Onboarding.objects.get(pk=graphql_onboarding.pk)
    assert onboarding.state == 'REVIEW'


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_success_update_organization_by_id(graphql_client, graphql_organization):
    executed = graphql_client.execute(
        '''
        mutation UpdateOrganizationById($input: OrganizationByIdInput!) {
            updateOrganizationById(input: $input) {
                data {
                    id
                    calendlyUrl
                }
            }
        }
        ''',
        variables={
            'input': {
                'id': graphql_organization.id,
                'description': 'some new updated description',
                'calendlyUrl': FAKE_CALENDLY_URL,
            }
        },
    )
    response = executed['data']['updateOrganizationById']
    assert response['data']['id'] == str(graphql_organization.id)
    assert response['data']['calendlyUrl'] == FAKE_CALENDLY_URL


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_failed_update_organization_by_id(graphql_client, graphql_organization):
    with raises(Exception) as excinfo:
        create_organization(name=TEST_ORG)

        executed = graphql_client.execute(
            '''
            mutation UpdateOrganizationById($input: OrganizationByIdInput!) {
                updateOrganizationById(input: $input) {
                    success
                    data {
                        id
                    }
                    error {
                        code
                        message
                    }
                }
            }
            ''',
            variables={
                'input': {
                    'id': graphql_organization.id,
                    'name': TEST_ORG,
                    'description': 'some new updated description',
                }
            },
        )

        response = executed['data']['updateOrganizationById']
        assert response['success'] is False
        assert excinfo == 'Organization name already exists'


@pytest.mark.functional()
def test_attach_default_report_template():
    organization = create_organization(name=TEST_ORG)
    template = attach_default_report_template(organization)
    assert str(template) == 'template_Test Org'


@pytest.mark.functional()
def test_create_org_default_flags():
    organization = create_organization(name=TEST_ORG)
    set_default_flags(organization)

    feature_flags = organization.feature_flags.all()

    for ff in feature_flags:
        if ff.name == AUDITS_FEATURE_FLAG.get('name'):
            # By default auditsFeatureFlag should be off
            assert ff.is_enabled is False

    assert len(organization.feature_flags.all()) == default_feature_flags_len


@pytest.mark.functional()
def tes_run_seed_base_profile():
    seed_file = File(open(SEED_FILE_PATH, "rb"))

    SeedProfile.objects.create(
        name='My New Profile Template',
        default_base=True,
        file=File(name='MySeedFile', file=seed_file),
    )

    organization = create_organization(name=TEST_ORG)
    seed_base_profile(organization)

    seed = Seed.objects.get(organization__id=organization.id)
    assert seed.status == DONE


@pytest.mark.functional()
def test_run_seed_base_profile_not_found():
    organization = create_organization(name=TEST_ORG)
    seed_base_profile(organization)

    seed = Seed.objects.filter(organization__id=organization.id).first()
    assert seed is None


@pytest.mark.functional()
def test_create_organization_drive(graphql_organization):
    organization = Organization.objects.create(name='Test Org', website='my-website')

    assert organization

    drive = create_organization_drive(organization)
    assert drive


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_onboarding_by_organization(graphql_client, graphql_organization):
    executed = graphql_client.execute(
        '''
       query OnboardingByOrganization($organizationId: UUID!) {
            onboardingByOrganization(organizationId: $organizationId) {
                setupSteps {
                    name
                    completed
                }
            }
        }
        ''',
        variables={'organizationId': str(graphql_organization.id)},
    )

    response = executed['data']['onboardingByOrganization']
    (first, second, third, fourth, fifth, sixth) = response['setupSteps']

    assert graphql_organization.onboarding is not None
    assert first['name'] == 'CONTROL_PRESCRIPTION'
    assert first['completed'] is False
    assert second['name'] == 'DOCUMENTATION_REVIEW'
    assert second['completed'] is False
    assert third['name'] == 'OPERATIONAL_MATURITY_REVIEW'
    assert third['completed'] is False
    assert fourth['name'] == 'SELECT_CERTIFICATIONS'
    assert fourth['completed'] is False
    assert fifth['name'] == 'SEED_RELEVANT_DOCUMENTS'
    assert fifth['completed'] is False
    assert sixth['name'] == 'ROADMAP_CONFIGURATION'
    assert sixth['completed'] is False


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_update_onboarding_step_completion(graphql_client, graphql_organization):
    executed = graphql_client.execute(
        '''
        mutation UpdateOnboardingStepCompletion(
            $input: OnboardingStepCompletionInput!
        ) {
        updateOnboardingStepCompletion(input: $input) {
            step {
                name
                completed
            }
        }
        }
        ''',
        variables={
            'input': {
                'organizationId': graphql_organization.id,
                'name': ONBOARDING_SETUP_STEP[5][0],
                'completed': True,
            }
        },
    )

    response = executed['data']['updateOnboardingStepCompletion']['step']

    assert response['name'] == 'ROADMAP_CONFIGURATION'
    assert response['completed'] is True


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_check_ins(graphql_client, graphql_organization, create_check_ins):
    executed = graphql_client.execute(
        '''
       query CheckIns(
            $id: UUID!
            $orderBy: OrderInputType,
            $pagination: PaginationInputType,
            $filter: [OrganizationCheckInFilterType]
            $searchCriteria: String
        ) {
            checkIns(
                id: $id
                orderBy: $orderBy
                pagination: $pagination
                filter: $filter
                searchCriteria: $searchCriteria
            ) {
                data {
                    id
                    date
                    cxParticipant {
                        id
                        firstName
                        lastName
                    }
                    customerParticipant
                    notes
                    actionItems
                }
            }
        }
        ''',
        variables={'id': str(graphql_organization.id), 'searchCriteria': FAKE_NOTE},
    )

    response = executed['data']['checkIns']['data']

    assert response[0]['cxParticipant']['firstName'] == 'Luis'
    assert response[0]['customerParticipant'] == 'Fake participant 1'
    assert response[0]['notes'] == FAKE_NOTE
    assert response[0]['actionItems'] == 'Fake action item 1'


@pytest.mark.functional(permissions=['user.add_concierge'])
def test_create_organization_check_in(graphql_client, graphql_organization):
    executed = graphql_client.execute(
        '''
       mutation CreateCheckIn($input: CreateOrganizationCheckInInput!) {
        createCheckin(input: $input) {
                success
                error {
                    code
                    message
                }
            }
        }
        ''',
        variables={
            "input": {
                "id": str(graphql_organization.id),
                "date": FAKE_DATE,
                "cxId": '',
                "customerParticipant": FAKE_PARTICIPANT,
                "notes": FAKE_NOTE,
                "actionItems": FAKE_ACTION_ITEM,
            }
        },
    )

    response = executed['data']['createCheckin']
    created_check_in = graphql_organization.check_ins.first()

    assert response['success'] is True
    assert response['error'] is None
    assert len(graphql_organization.check_ins.all()) == 1
    assert created_check_in.customer_participant == FAKE_PARTICIPANT


@pytest.mark.functional(permissions=['user.remove_concierge'])
def test_delete_organization_check_in(
    graphql_client, graphql_organization, create_check_ins
):
    executed = graphql_client.execute(
        '''
       mutation DeleteCheckIn($input: DeleteOrganizationCheckInInput!) {
            deleteCheckin(input: $input) {
                success
                error {
                    code
                    message
                }
            }
        }
        ''',
        variables={"input": {"checkInIds": ["1"]}},
    )

    response = executed['data']['deleteCheckin']
    deleted = graphql_organization.check_ins.filter(active=False)

    assert response['success'] is True
    assert response['error'] is None
    assert len(deleted) == 1


@pytest.mark.functional(permissions=['organization.view_apitokenhistory'])
def test_get_list_api_tokens(graphql_client, graphql_organization):
    user = _api_token_user(graphql_organization)
    _create_api_token_record(graphql_organization, user)
    executed = graphql_client.execute(
        GET_API_TOKENS,
    )

    response = executed['data']['apiTokens']
    assert len(response) > 0
    assert response[0]['name'] == 'test'


@pytest.mark.functional(permissions=['organization.delete_apitokenhistory'])
def test_delete_api_token(graphql_client, graphql_organization):
    user = _api_token_user(graphql_organization)
    api_token_record = _create_api_token_record(graphql_organization, user)
    executed = graphql_client.execute(
        DELETE_API_TOKEN, variables={'id': api_token_record.id}
    )
    response = executed['data']['deleteApiToken']
    assert response['apiTokenId'] == api_token_record.id


@pytest.mark.functional(permissions=['organization.add_apitokenhistory'])
def test_create_api_token(graphql_client, graphql_organization):
    create_test_group()
    executed = graphql_client.execute(CREATE_API_TOKEN, variables={'name': 'test-name'})
    assert executed['data']['createApiToken']['id'] == 1


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_move_org_out_of_onboarding(graphql_client, graphql_organization):
    graphql_organization.onboarding.update(state='REVIEW')

    executed = graphql_client.execute(
        MOVE_ORG_OUT_OF_ONBOARDING,
        variables={'input': dict(organizationId=graphql_organization.id)},
    )

    response = executed['data']['moveOrgOutOfOnboarding']

    # using this function here, because signals shouldn't be tested
    handle_review_ready(graphql_organization.onboarding.get())

    onboarding = graphql_organization.onboarding.get()
    for step in onboarding.setup_steps.all():
        assert step.completed is True
    assert onboarding.state == 'READY'
    assert response['success'] is True


@pytest.mark.functional(permissions=['integration.delete_connectionaccount'])
def test_delete_org(graphql_user, graphql_organization):
    create_connection_account(
        'testing-to-delete',
        alias='testing_deleted_connection',
        organization=graphql_organization,
        authentication={},
    )

    delete_organization_data(graphql_organization, graphql_user)


def _create_api_token_record(organization, user):
    return ApiTokenHistory.objects.create(
        name='test',
        api_key='eydnsjdnjsdjsaldd.ffhfbsdhfdf.dfdsfsdf',
        token_identifier=uuid.uuid4(),
        organization=organization,
        created_by=user,
        created_at=datetime.now(),
        expires_at=datetime.now(),
    )


def _api_token_user(organization):
    return create_user(
        organization,
        email='test+2@heylaika.com',
        permissions=[
            'organization.delete_apitokenhistory',
            'organization.view_apitokenhistory',
            'organization.add_apitokenhistory',
        ],
        first_name='Test',
    )


@pytest.mark.functional(permissions=['organization.change_organization'])
def test_complete_organization_onboarding(graphql_client, graphql_organization):
    graphql_organization.onboarding.update(state='READY')

    executed = graphql_client.execute(COMPLETE_ONBOARDING)

    response = executed['data']['completeOnboarding']

    onboarding = graphql_organization.onboarding.get()

    assert onboarding.state == 'COMPLETED'
    assert response['success'] is True


@pytest.mark.functional()
def test_fail_complete_organization_onboarding(graphql_client, graphql_organization):
    graphql_organization.onboarding.update(state='READY')

    executed = graphql_client.execute(COMPLETE_ONBOARDING)

    response = executed['data']['completeOnboarding']

    onboarding = graphql_organization.onboarding.get()

    assert onboarding.state != 'COMPLETED'
    assert response is None


@pytest.mark.functional(permissions=['organization.change_organization'])
def test_update_onboarding_v2_state(graphql_client, graphql_organization):
    graphql_organization.onboarding.update(state_v2=QUESTIONNAIRE)

    executed = graphql_client.execute(
        UPDATE_ONBOARDING_V2_STATE, variables={'stateV2': ARCHITECT_MEETING}
    )

    response = executed['data']['updateOnboardingV2State']

    onboarding = graphql_organization.onboarding.get()

    assert onboarding.state_v2 == ARCHITECT_MEETING
    assert response['success'] is True


@pytest.mark.functional()
def test_get_onboarding_state_v2(graphql_client, graphql_organization):
    onboarding = graphql_organization.onboarding.get()

    assert onboarding.state_v2 == QUESTIONNAIRE
