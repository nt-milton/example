from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from control.constants import STATUS
from control.models import Control, ControlGroup, RoadMap
from control.tests.factory import create_control
from organization.constants import TDDQ_METADATA_TABLE
from organization.models import (
    ONBOARDING,
    ONBOARDING_SETUP_STEP,
    Organization,
    handle_review_ready,
)
from organization.roadmap_helper import (
    get_roadmap_backlog_implemented_controls,
    get_roadmap_backlog_total_controls,
    get_roadmap_groups_implemented_controls,
    get_roadmap_groups_total_controls,
)
from organization.tasks import (
    create_laika_app_super_admin_user,
    create_super_admin_users,
    tddq_execution,
)
from organization.tddq_helper import (
    get_airtable_records,
    get_formatted_data,
    get_options_from_list,
)
from organization.tests.test_utils import disconnect_org_and_seeder_post_savings
from user.models import User

RECORD_ID_MOCK = '12345kls'
DATETIME_MOCK = '2022-08-17T17:16:00.000Z'
METADATA_MOCK = [
    {
        'id': RECORD_ID_MOCK,
        'createdTime': DATETIME_MOCK,
        'fields': {
            'Criticality': 'Low',
            'Response Type': 'Menu (Multiple Choice)',
            'Key Indicators': 'General',
            'Question': 'Please describe your primary responsibilities',
        },
    }
]
RECORDS_MOCK = [
    {
        'Criticality': 'Low',
        'Response Type': 'Menu (Multiple Choice)',
        'Key Indicators': 'General',
        'Question': 'And their last name?',
        'Organization ID': '50d1833e-de05-4d84-8255-972ad3c9bd9c',
        'Question Response': 'Test',
    },
    {
        'Criticality': 'Low',
        'Response Type': 'Menu (Multiple Choice)',
        'Key Indicators': 'General',
        'Question': 'First name?',
        'Organization ID': '50d1833e-de05-4d84-8255-972ad3c9bd9c',
        'Question Response': 'Test Name',
    },
]
AIRTABLE_RECORDS_MOCK = [
    {
        'id': RECORD_ID_MOCK,
        'createdTime': DATETIME_MOCK,
        'fields': {
            'Question Response': 'test@heylaika.com',
            'Question': 'Email address?',
            'Key Indicators': 'Gap Analysis',
            'Organization Name': 'Test Org',
            'Organization ID': '50d1833e-de05-4d84-8255-972ad3c9bd9c',
            'Criticality': 'High',
            'Response Type': 'Menu (Multiple Choice)',
        },
    },
    {
        'id': RECORD_ID_MOCK,
        'createdTime': DATETIME_MOCK,
        'fields': {
            'Question Response': 'Test',
            'Question': 'And their last name?',
            'Key Indicators': 'General',
            'Organization Name': 'Test Org',
            'Organization ID': '50d1833e-de05-4d84-8255-972ad3c9bd9c',
            'Criticality': 'Low',
            'Response Type': 'Menu (Multiple Choice)',
        },
    },
]


FORMATTED_DATA = [
    {
        'Organization ID': '94090cd7-40fd-4667-b02e-287bd33bd3fc',
        'Please describe your primary responsibilities': 'CEO',
        'Criticality': 'Low',
        'Response Type': 'Menu (Multiple Choice)',
        'Key Indicators': 'General',
        'Question': 'Please describe your primary responsibilities',
    }
]


@pytest.fixture()
def roadmap_controls(graphql_organization):
    roadmap = RoadMap.objects.create(organization=graphql_organization)
    group = ControlGroup.objects.create(
        roadmap=roadmap,
        name="Group 1",
        reference_id=None,
        due_date=None,
        sort_order=1,
    )

    backlog_controls = Control.objects.filter(
        organization=graphql_organization, group=None
    )

    implemented_control_1 = create_control(
        organization=graphql_organization,
        reference_id="CTR-001-SOC",
        name='Control Test 1',
        description='Control Test 1',
        display_id=1,
        status=STATUS['IMPLEMENTED'],
    )
    create_control(
        organization=graphql_organization,
        reference_id="CTR-002-SOC",
        name='Control Test 2',
        description='Control Test 2',
        display_id=2,
        status=STATUS['IMPLEMENTED'],
    )
    not_implemented_control_1 = create_control(
        organization=graphql_organization,
        reference_id="CTR-003-SOC",
        name='Control Test 3',
        description='Control Test 3',
        display_id=3,
        status=STATUS['NOT IMPLEMENTED'],
    )
    create_control(
        organization=graphql_organization,
        reference_id="CTR-004-SOC",
        name='Control Test 4',
        description='Control Test 4',
        display_id=4,
        status=STATUS['NOT IMPLEMENTED'],
    )

    group.controls.add(implemented_control_1, not_implemented_control_1)

    return roadmap, backlog_controls


@pytest.fixture()
def onboarding(graphql_organization):
    graphql_organization.state = ONBOARDING
    graphql_organization.save()
    return graphql_organization.onboarding.first()


def typeform_answer(answer_type, answer_value):
    return {'field': {'ref': answer_value}, "type": answer_type}


@pytest.mark.django_db
def test_create_setup_steps_on_onboarding_creation(onboarding):
    steps = onboarding.setup_steps.all()

    assert len(steps) == 6
    assert steps[0].name == ONBOARDING_SETUP_STEP[0][0]
    assert steps[1].name == ONBOARDING_SETUP_STEP[1][0]
    assert steps[2].name == ONBOARDING_SETUP_STEP[2][0]
    assert steps[3].name == ONBOARDING_SETUP_STEP[3][0]
    assert steps[4].name == ONBOARDING_SETUP_STEP[4][0]
    assert steps[5].name == ONBOARDING_SETUP_STEP[5][0]


def complete_all_steps(onboarding):
    steps = onboarding.setup_steps.all()

    for step in steps:
        step.completed = True
        step.save()


@pytest.mark.django_db
@patch('organization.models.send_review_starting_emails')
def test_setup_step_change_onboarding_v1_status(
    send_review_starting_emails_mock, onboarding
):
    onboarding.state = 'REVIEW'
    onboarding.save()
    complete_all_steps(onboarding)

    handle_review_ready(onboarding)
    send_review_starting_emails_mock.assert_called_once()

    assert onboarding.state == 'READY'


@pytest.mark.django_db
@patch('organization.models.send_review_ready_email')
def test_setup_step_change_onboarding_v2_status(
    send_review_ready_email_mock, onboarding
):
    onboarding.state_v2 = 'ARCHITECT_MEETING'
    onboarding.save()
    complete_all_steps(onboarding)

    handle_review_ready(onboarding)
    send_review_ready_email_mock.assert_called_once()

    assert onboarding.state_v2 == 'READY'


@pytest.mark.django_db
@patch('user.helpers.manage_cognito_user')
def test_create_new_organization_signals(
    manage_cognito_user_mock,
    graphql_user,
):
    manage_cognito_user_mock.return_value = (graphql_user, '12345asdf')
    disconnect_org_and_seeder_post_savings()
    organization = Organization.objects.create(
        name='Fake Org',
        website='https://fake.org',
        customer_success_manager_user=graphql_user,
        compliance_architect_user=graphql_user,
    )

    create_super_admin_users(organization)
    manage_cognito_user_mock.assert_called_once()

    assert User.objects.count() == 2
    assert User.objects.filter(email='test+fake@heylaika.com').count() == 1


@pytest.mark.django_db
@patch('user.helpers.manage_cognito_user')
@patch('organization.tasks.send_emails_to_super_admin', return_value=True)
def test_create_laika_app_super_admin_user(
    send_emails_to_admins_mock,
    manage_cognito_user_mock,
    graphql_user,
):
    manage_cognito_user_mock.return_value = (graphql_user, '12345asdf')
    disconnect_org_and_seeder_post_savings()
    organization = Organization.objects.create(
        name='Fake Org',
        website='https://fake.org',
        customer_success_manager_user=graphql_user,
        compliance_architect_user=graphql_user,
    )

    create_laika_app_super_admin_user(organization)
    manage_cognito_user_mock.assert_called_once()
    send_emails_to_admins_mock.assert_called_once()

    assert User.objects.count() == 2
    assert User.objects.filter(email='admin+laikaapp+fake@heylaika.com').count() == 1


@pytest.mark.django_db
def test_validate_maximum_length_name_field():
    new_name = 'x' * 256
    organization = Organization(name=new_name)
    with pytest.raises(ValidationError):
        organization.full_clean()
        organization.save()


@pytest.mark.django_db
@patch('organization.tddq_helper.execute_airtable_request', return_value=METADATA_MOCK)
def test_get_airtable_records(execute_airtable_request_mock, graphql_organization):
    response = get_airtable_records(TDDQ_METADATA_TABLE, '')
    execute_airtable_request_mock.assert_called_once()
    assert response is not None


@pytest.mark.django_db
def test_get_formatted_data(graphql_organization):
    raw_answers = {
        'id': RECORD_ID_MOCK,
        'createdTime': DATETIME_MOCK,
        'fields': {
            'Organization ID': str(graphql_organization.id),
            'Please describe your primary responsibilities': ['CEO'],
        },
    }
    formatted = get_formatted_data(raw_answers, METADATA_MOCK)

    assert len(formatted) == 1
    assert formatted[0]['Question Response'] == 'CEO'

    raw_answers['fields'] = {
        'Organization ID': str(graphql_organization.id),
        'Please describe your primary responsibilities': 'CEO',
    }
    formatted = get_formatted_data(raw_answers, METADATA_MOCK)
    assert len(formatted) == 1
    assert formatted[0]['Question Response'] == 'CEO'

    raw_answers['fields'] = {
        'Organization ID': str(graphql_organization.id),
        'Please describe your primary responsibilities': True,
    }
    formatted = get_formatted_data(raw_answers, METADATA_MOCK)
    assert len(formatted) == 1
    assert formatted[0]['Question Response'] == 'True'


@pytest.mark.django_db
@patch(
    'organization.tddq_helper.execute_airtable_request',
    return_value=AIRTABLE_RECORDS_MOCK,
)
@patch('organization.tddq_helper.get_formatted_data', return_value=FORMATTED_DATA)
def test_tddq_execution(
    get_formatted_data_mock,
    execute_airtable_request_mock,
):
    tddq_execution('')
    assert get_formatted_data_mock.assert_called
    execute_airtable_request_mock.assert_called()


def test_get_options_from_list():
    options, attachments = get_options_from_list(['A response'])
    assert options == ['A response']
    assert not attachments

    options, attachments = get_options_from_list(
        [{'url': 'https://lin.com', 'filename': 'myfile.png'}]
    )
    assert len(options) == 1
    assert len(attachments) == 1


@pytest.mark.django_db
def test_get_roadmap_total_controls(roadmap_controls):
    roadmap, backlog_controls = roadmap_controls
    total_backlog_controls = get_roadmap_backlog_total_controls(backlog_controls)
    total_group_controls = get_roadmap_groups_total_controls(roadmap.groups.all())

    assert total_backlog_controls == 2
    assert total_group_controls == 2


@pytest.mark.django_db
def test_get_roadmap_implemented_controls(roadmap_controls):
    roadmap, backlog_controls = roadmap_controls
    backlog_implemented_controls = get_roadmap_backlog_implemented_controls(
        backlog_controls
    )
    group_implemented_controls = get_roadmap_groups_implemented_controls(
        roadmap.groups.all()
    )

    assert group_implemented_controls == 1
    assert backlog_implemented_controls == 1
