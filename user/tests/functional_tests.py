import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import django.utils.timezone as timezone
import pytest
from django.contrib.auth.models import Group

import user.errors as errors
from action_item.models import ActionItem
from alert.constants import ALERT_TYPES
from alert.models import Alert
from feature.constants import okta_feature_flag
from integration.checkr.mapper import CHECKR_SYSTEM
from laika.settings import LAIKA_CONCIERGE_REDIRECT, ORIGIN_LOCALHOST
from laika.tests.utils import file_to_base64
from objects.system_types import (
    ACCOUNT,
    BACKGROUND_CHECK,
    USER,
    resolve_laika_object_type,
)
from objects.tests.factory import create_lo_with_connection_account
from organization.models import Organization
from organization.tests import create_organization
from policy.models import Policy
from policy.tests.factory import create_published_empty_policy
from user.concierge_helpers import send_concierge_user_email_invitation
from user.constants import (
    AUDITOR,
    AUDITOR_ADMIN,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_SUPER_ADMIN,
    ROLE_VIEWER,
    SALESPERSON,
    USER_ROLES,
)
from user.models import (
    BACKGROUND_CHECK_STATUS_PENDING,
    DISCOVERY_STATE_CONFIRMED,
    DISCOVERY_STATE_IGNORED,
    DISCOVERY_STATE_NEW,
    Concierge,
    Partner,
    PartnerType,
    User,
)
from user.mutations import get_old_and_new_cognito_role
from user.permissions import add_concierge_user_to_group
from user.tests import create_candidate_user, create_team, create_user
from user.utils.name import get_capitalized_name

from .factory import DEFAULT_USER_PREFERENCES, create_lo_user
from .mocks import COGNITO_NEW_USER
from .queries import (
    BULK_INVITE_USER,
    DELEGATE_UNINVITED_USER_INTEGRATION,
    DELEGATE_USER_INTEGRATION,
    DELETE_USERS,
    GET_AUDITORS,
    GET_CONCIERGE_PARTNERS,
    GET_CSM_AND_CA_USERS,
    GET_DISCOVERED_PEOPLE,
    GET_USER,
    GET_USERS,
    GET_USERS_BY_ROLE,
    GET_USERS_ORG_INPUT,
    GET_USERS_WITH_LO_IDS,
    INVITE_USER_TO_ORGANIZATION,
    RESEND_INVITATION,
    UPDATE_USER,
    UPDATE_USER_EMAIL,
    UPDATE_USER_PREFERENCES,
)

EMAIL = 'laika-test@test.com'
TEST_EMAIL = 'ynonoamine@bambotv.com'
USER_PREFERENCES = '{"onboarding":{"currentPage":3.8}}'
TASK_DESCRIPTION = 'Video training description'
USER_EMAIL = 'john@superadmin.com'


@pytest.fixture()
def users(graphql_organization):
    super_admin_user = create_user(
        graphql_organization,
        email=USER_EMAIL,
        role=ROLE_SUPER_ADMIN,
        first_name='johnZ',
        last_name='doeZ',
    )
    admin_user = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
    )
    sales_user = create_user(
        graphql_organization,
        email='john@example.com',
        role=SALESPERSON,
        first_name='johnB',
        last_name='doeB',
    )

    return admin_user, sales_user, super_admin_user


@pytest.fixture
def auditors(graphql_organization):
    auditor_admin = create_user(
        graphql_organization,
        email='auditor_admin@heylaika.com',
        role=AUDITOR_ADMIN,
        first_name='john',
    )
    auditor = create_user(
        graphql_organization,
        email='auditor@heylaika.com',
        role=AUDITOR,
        first_name='john',
    )
    return auditor, auditor_admin


@pytest.fixture()
def user(graphql_organization):
    admin_user = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        username='username1',
    )
    return admin_user


@pytest.fixture()
def lo_users(graphql_organization):
    lo_user1 = create_lo_user(
        graphql_organization, email=USER_EMAIL, source_system='jira', id='111'
    )
    lo_user2 = create_lo_user(
        graphql_organization, email=USER_EMAIL, source_system='git', id='222'
    )
    return lo_user1, lo_user2


@pytest.fixture()
def lo_background_check(graphql_organization):
    return create_lo_with_connection_account(
        graphql_organization,
        data={
            'Id': 1,
            'Link to People Table': {
                "id": 276,
                "email": "leo+messi+1@heylaika.com",
                "lastName": "messi",
                "username": "9cfd6c8d-6373-4973-979f-8cd58652d9ac",
                "firstName": "leo",
            },
        },
        type_name=BACKGROUND_CHECK.type,
    )


@pytest.fixture()
def email_users(graphql_organization):
    admin = create_user(
        graphql_organization,
        email='john_active@example.com',
        role=ROLE_ADMIN,
        first_name='johnA',
        last_name='doeA',
        is_active=True,
    )
    admin_inactive = create_user(
        graphql_organization,
        email='john_inactive@example.com',
        role=ROLE_ADMIN,
        first_name='johnB',
        last_name='doeB',
        is_active=False,
    )

    return {'admin': admin, 'admin_inactive': admin_inactive}


@pytest.fixture()
def candidate_users(graphql_organization):
    confirmed_user = create_candidate_user(
        graphql_organization,
        email='john@confirmed.com',
        role=ROLE_SUPER_ADMIN,
        first_name='johnZ',
        last_name='doeZ',
    )
    new_user_1 = create_candidate_user(
        graphql_organization,
        email='john@new.com',
        role=ROLE_VIEWER,
        first_name='johnC',
        last_name='doeC',
        discovery_state=DISCOVERY_STATE_NEW,
        is_active=False,
    )
    new_user_2 = create_candidate_user(
        graphql_organization,
        email='john@ignored.com',
        role=SALESPERSON,
        first_name='johnB',
        last_name='doeB',
        discovery_state=DISCOVERY_STATE_NEW,
    )
    return confirmed_user, new_user_1, new_user_2


@pytest.fixture()
def team(graphql_organization):
    return create_team(organization=graphql_organization)


@pytest.fixture
def organization_with_okta_flag_on() -> Organization:
    return create_organization(flags=[okta_feature_flag], name='Test Org')


@pytest.fixture
def okta_user(organization_with_okta_flag_on) -> User:
    return create_user(organization_with_okta_flag_on, email='john@admin.com')


@pytest.fixture
def organization_with_out_okta_flag_on():
    return create_organization(flags=[], name='Test Org')


@pytest.fixture
def cognito_user(organization_with_out_okta_flag_on):
    return create_user(organization_with_out_okta_flag_on, email='john@admin.com')


def _get_collection_users(response):
    return response['data']['users']['data']


def _get_collection_users_by_role(response):
    return response['data']['usersByRole']['data']


def _get_user_updated_collection(response):
    return response['data']['updateUser']['data']


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_all_users_with_search_criteria(graphql_client, users):
    response = graphql_client.execute(GET_USERS, variables={'searchCriteria': 'john'})

    collection = _get_collection_users(response)
    assert len(collection) == 3


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_all_users(graphql_client, users):
    response = graphql_client.execute(GET_USERS, variables={'allUsers': True})

    collection = _get_collection_users(response)
    first_names = [u['firstName'] for u in collection if u == '']
    assert sorted(first_names) == first_names
    assert ROLE_SUPER_ADMIN in [c['role'] for c in collection]


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_all_users_with_status_pending(graphql_client, graphql_organization):
    create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now(),
    )

    response = graphql_client.execute(GET_USERS)

    users = response['data']['users']['data']
    user = users[1]
    assert user['status'] == 'PENDING_INVITATION'


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_all_users_with_status_invitation_expired(
    graphql_client, graphql_organization
):
    THIRTY_FIVE_DAYS = 35
    create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now() - timedelta(THIRTY_FIVE_DAYS),
    )

    response = graphql_client.execute(GET_USERS)

    users = response['data']['users']['data']
    user = users[1]

    assert user['status'] == 'INVITATION_EXPIRED'


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_all_users_with_status_password_expired(
    graphql_client, graphql_organization
):
    create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=None,
        password_expired=True,
    )

    response = graphql_client.execute(GET_USERS)

    users = response['data']['users']['data']
    user = users[1]

    assert user['status'] == 'PASSWORD_EXPIRED'


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_all_users_with_status_active(graphql_client, graphql_organization):
    user = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now(),
    )
    user.last_login = datetime.now()
    user.save()

    response = graphql_client.execute(GET_USERS)

    users = response['data']['users']['data']
    user = users[1]

    assert user['status'] == 'ACTIVE'


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_all_users_by_organization(graphql_client, graphql_organization):
    response = graphql_client.execute(
        GET_USERS_ORG_INPUT,
        variables={'allUsers': True, 'organizationId': str(graphql_organization.id)},
    )

    collection = _get_collection_users(response)
    first_names = [u['firstName'] for u in collection if u == '']
    assert sorted(first_names) == first_names


@pytest.mark.functional()
def test_get_user_by_id(graphql_client, user):
    response = graphql_client.execute(GET_USER, variables={'id': user.id})
    assert response['data']['user']['success'] is True


@pytest.mark.functional()
def test_get_user_by_username(graphql_client, user):
    response = graphql_client.execute(GET_USER, variables={'id': 'username1'})
    assert response['data']['user']['success'] is True


@pytest.mark.functional()
def test_get_user_by_email(graphql_client, user):
    response = graphql_client.execute(GET_USER, variables={'email': user.email})
    assert response['data']['user']['success'] is True


@pytest.mark.functional()
def test_get_user_by_id_not_user_found(graphql_client):
    response = graphql_client.execute(GET_USER, variables={'id': '1111'})
    assert response['data']['user']['success'] is False


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_users_exclude_super_admin(graphql_client, users):
    response = graphql_client.execute(GET_USERS)

    collection = _get_collection_users(response)
    first_names = [u['firstName'] for u in collection if u == '']
    assert sorted(first_names) == first_names
    assert ROLE_SUPER_ADMIN not in [c['role'] for c in collection if c == '']


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_exclude_users_with_roles(graphql_client, users):
    response = graphql_client.execute(
        GET_USERS,
        variables={
            'searchCriteria': 'john',
            'filter': dict(excludeRoles=[SALESPERSON]),
        },
    )
    collection = _get_collection_users(response)
    assert SALESPERSON not in [c['role'] for c in collection]


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_users_by_role(graphql_client, users):
    response = graphql_client.execute(
        GET_USERS_BY_ROLE, variables={'filter': dict(rolesIn=[SALESPERSON])}
    )

    collection = _get_collection_users_by_role(response)
    assert SALESPERSON in [c['role'] for c in collection]


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_users_by_role_excluding(graphql_client, graphql_organization):
    response = graphql_client.execute(
        GET_USERS_BY_ROLE,
        variables={
            'filter': dict(
                excludeRoles=[ROLE_VIEWER], organizationId=str(graphql_organization.id)
            )
        },
    )

    collection = _get_collection_users_by_role(response)
    assert ROLE_VIEWER not in [c['role'] for c in collection]


@pytest.mark.functional(permissions=['user.change_user'])
def test_update_user(graphql_client, graphql_organization):
    create_user(
        graphql_organization,
        email='john@heylaika.com',
        role=ROLE_VIEWER,
        first_name='johnZ',
        last_name='doeZ',
    )

    with patch('laika.aws.cognito.cognito'), patch(
        'laika.okta.api.OktaApi.get_user_by_email'
    ):
        response = graphql_client.execute(
            UPDATE_USER,
            variables={'input': dict(email='john@heylaika.com', role=ROLE_VIEWER)},
        )
        assert response['data']['updateUser']['success']
        assert response['data']['updateUser']['error'] is None


@pytest.mark.functional(permissions=['user.change_user'])
def test_update_user_preferences_error(graphql_client, users):
    user = users[-1]
    response = graphql_client.execute(
        UPDATE_USER,
        variables={
            'input': dict(
                email=user.email, userPreferences=json.dumps({'collapsedMenu': True})
            )
        },
    )
    assert not response['data']['updateUser']['success']


@pytest.mark.functional(permissions=['user.change_user'])
def test_update_user_email(graphql_client, email_users):
    user = email_users['admin_inactive']
    response = graphql_client.execute(
        UPDATE_USER_EMAIL,
        variables={'input': dict(currentEmail=user.email, newEmail='test@test.com')},
    )
    assert response['data']['updateUserEmail']['success']
    assert response['data']['updateUserEmail']['error'] is None


@pytest.mark.functional(permissions=['user.change_user'])
def test_update_user_email_active_user(graphql_client, email_users):
    user = email_users['admin']
    response = graphql_client.execute(
        UPDATE_USER_EMAIL,
        variables={'input': dict(newEmail=user.email, currentEmail=user.email)},
    )
    error_message = response['data']['updateUserEmail']['error']['message']
    assert error_message == errors.CANNOT_UPDATE_USER


@pytest.mark.functional(permissions=['user.change_user'])
def test_update_user_current_email_error(graphql_client, email_users):
    user = email_users['admin_inactive']
    response = graphql_client.execute(
        UPDATE_USER_EMAIL,
        variables={
            'input': dict(
                currentEmail=user.email,
            )
        },
    )
    errors = response['errors']
    message = errors[0]['message']

    assert response['errors']
    assert (
        message
        == 'Variable "$input" got invalid value {"currentEmail": "'
        + user.email
        + '"}.\nIn field "newEmail": Expected "String!", found null.'
    )


@pytest.mark.functional(permissions=['user.change_user'])
def test_update_user_new_email_error(graphql_client, email_users):
    user = email_users['admin_inactive']
    response = graphql_client.execute(
        UPDATE_USER_EMAIL,
        variables={
            'input': dict(
                newEmail=user.email,
            )
        },
    )
    errors = response['errors']
    message = errors[0]['message']

    assert response['errors']
    assert (
        message
        == 'Variable "$input" got invalid value {"newEmail": "'
        + user.email
        + '"}.\nIn field "currentEmail": Expected "String!", found null.'
    )


@pytest.mark.functional()
def test_update_user_email_no_change_permission(graphql_client, email_users):
    user = email_users['admin_inactive']
    response = graphql_client.execute(
        UPDATE_USER_EMAIL,
        variables={'input': dict(email=user.email, newEmail='test@test.com')},
    )
    assert response['errors']


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_csm_and_ca_users(graphql_client):
    response = graphql_client.execute(
        GET_CSM_AND_CA_USERS,
    )
    assert response['data']['csmAndCaUsers']


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_auditors(graphql_client):
    response = graphql_client.execute(GET_AUDITORS)
    assert response['data']['allAuditors']


@pytest.mark.functional()
def test_update_user_preferences(graphql_client, graphql_organization):
    user = User.objects.get(
        email=graphql_client.context['user'].email,
        organization=graphql_client.context['user'].organization,
    )
    expected_user_preference = {'profile': {'alerts': 'Never', 'emails': 'Daily'}}
    assert user.user_preferences == expected_user_preference
    updated_preferences = {'profile': {'alerts': 'Never', 'emails': 'Never'}}
    response = graphql_client.execute(
        UPDATE_USER_PREFERENCES,
        variables={
            'input': dict(
                email=user.email, userPreferences=json.dumps(updated_preferences)
            )
        },
    )
    data = response['data']['updateUserPreferences']['data']['userPreferences']
    assert data == json.dumps(updated_preferences)


@pytest.mark.functional()
def test_clean_bad_filter_values_in_update_user_preferences(
    graphql_client, graphql_organization
):
    user = User.objects.get(
        email=graphql_client.context['user'].email,
        organization=graphql_client.context['user'].organization,
    )

    resolve_laika_object_type(graphql_organization, USER)
    resolve_laika_object_type(graphql_organization, ACCOUNT)

    updated_preferences_with_lo_filters = {
        'profile': {'alerts': 'Never', 'emails': 'Never'},
        "laikaObjectsFilter": {
            "user": [
                {
                    "id": "First Name",
                    "value": "otto",
                    "column": "First Name",
                    "component": "text",
                    "condition": "contains",
                    "columnType": "TEXT",
                }
            ],
            "account": [
                {
                    "id": "First Name",
                    "value": "otto",
                    "column": "First Name",
                    "component": "text",
                    "condition": "contains",
                    "columnType": "TEXT",
                }
            ],
        },
    }

    expected_user_preferences_with_lo_filters = {
        'profile': {'alerts': 'Never', 'emails': 'Never'},
        "laikaObjectsFilter": {
            "user": [
                {
                    "id": "First Name",
                    "value": "otto",
                    "column": "First Name",
                    "component": "text",
                    "condition": "contains",
                    "columnType": "TEXT",
                }
            ]
        },
    }

    response = graphql_client.execute(
        UPDATE_USER_PREFERENCES,
        variables={
            'input': dict(
                email=user.email,
                userPreferences=json.dumps(updated_preferences_with_lo_filters),
            )
        },
    )

    data = response['data']['updateUserPreferences']['data']['userPreferences']
    assert json.dumps(expected_user_preferences_with_lo_filters) == data


@pytest.mark.functional()
def test_get_capitalized_name(graphql_client, users):
    user = users[-1]
    name = get_capitalized_name(user.first_name, user.last_name)
    large_name = get_capitalized_name('John Z', 'Doe W')
    assert name == 'Johnz Doez'
    assert large_name == 'John Doe'


@pytest.mark.functional(permissions=['user.view_user'])
def test_candidate_people_query_with_discovery_state_new(
    graphql_client, candidate_users
):
    query_response = graphql_client.execute(GET_DISCOVERED_PEOPLE)
    candidate_people = query_response['data']['discoveredPeople']
    assert len(candidate_people) > 0


@pytest.mark.functional(permissions=['user.view_user'])
def test_candidate_people_query_without_confirmed_discovery_state(
    graphql_client, candidate_users
):
    query_response = graphql_client.execute(GET_DISCOVERED_PEOPLE)
    candidate_people = query_response['data']['discoveredPeople']['data']
    assert DISCOVERY_STATE_CONFIRMED not in [
        user['discoveryState'] for user in candidate_people
    ]


@pytest.mark.functional(permissions=['user.view_user'])
def test_candidate_people_query_without_confirmed_users(
    graphql_client, candidate_users
):
    user = candidate_users[0]
    query_response = graphql_client.execute(GET_DISCOVERED_PEOPLE)
    candidate_people = query_response['data']['discoveredPeople']['data']
    assert user.email not in [user['email'] for user in candidate_people]


@pytest.mark.functional(permissions=['user.add_user'])
def test_confirm_people_candidates_mutation(graphql_client, candidate_users):
    with patch('user.mutations.invite_user_m') as mock_invite:
        _, new_to_confirm, new_to_ignore = candidate_users

        query_resp = graphql_client.execute(
            CONFIRM_PEOPLE_CANDIDATE_MUTATION,
            variables={
                'confirmedPeopleCandidates': [
                    {'email': new_to_confirm.email, 'role': USER_ROLES['CONTRIBUTOR']}
                ],
                'ignoredPeopleEmails': [new_to_ignore.email],
            },
        )
        people_emails = query_resp['data']['confirmPeopleCandidates']['peopleEmails']
        new_to_ignore.refresh_from_db()
        new_to_confirm.refresh_from_db()
        assert len(people_emails) == 1
        assert new_to_ignore.discovery_state == DISCOVERY_STATE_IGNORED
        assert new_to_confirm.discovery_state == DISCOVERY_STATE_CONFIRMED
        mock_invite.assert_called_once()


@pytest.mark.functional(permissions=['user.add_user'])
def test_confirm_people_candidates_and_single_match_lo_background_check(
    graphql_client, candidate_users, graphql_organization
):
    Group.objects.create(name='premium_viewer')
    laika_objects, _ = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data=[
            {'First Name': 'johnC', 'Last Name': 'doeC', 'Link to People Table': None},
            {'First Name': 'johnB', 'Last Name': 'doeB', 'Link to People Table': None},
        ],
    )
    with patch('user.mutations.invite_user_m') as mock_invite:
        _, new_to_confirm, new_to_ignore = candidate_users

        query_resp = graphql_client.execute(
            CONFIRM_PEOPLE_CANDIDATE_MUTATION,
            variables={
                'confirmedPeopleCandidates': [
                    {'email': new_to_confirm.email, 'role': USER_ROLES['CONTRIBUTOR']}
                ],
                'ignoredPeopleEmails': [new_to_ignore.email],
            },
        )
        people_emails = query_resp['data']['confirmPeopleCandidates']['peopleEmails']
        new_to_ignore.refresh_from_db()
        new_to_confirm.refresh_from_db()
        assert len(people_emails) == 1
        assert new_to_ignore.discovery_state == DISCOVERY_STATE_IGNORED
        assert new_to_confirm.discovery_state == DISCOVERY_STATE_CONFIRMED
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER')
        alert = Alert.objects.filter(type=alert_type)
        assert alert.count() == 1
        mock_invite.assert_called_once()


@pytest.mark.functional(permissions=['user.add_user'])
def test_confirm_people_candidates_and_multiple_match_lo_background_check(
    graphql_client, candidate_users, graphql_organization
):
    Group.objects.create(name='premium_viewer')
    laika_objects, _ = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data=[
            {'First Name': 'johnC', 'Last Name': 'doeC', 'Link to People Table': None},
            {'First Name': 'johnC', 'Last Name': 'doeC', 'Link to People Table': None},
        ],
    )
    with patch('user.mutations.invite_user_m') as mock_invite:
        _, new_to_confirm, new_to_ignore = candidate_users

        query_resp = graphql_client.execute(
            CONFIRM_PEOPLE_CANDIDATE_MUTATION,
            variables={
                'confirmedPeopleCandidates': [
                    {'email': new_to_confirm.email, 'role': USER_ROLES['CONTRIBUTOR']}
                ],
                'ignoredPeopleEmails': [new_to_ignore.email],
            },
        )
        people_emails = query_resp['data']['confirmPeopleCandidates']['peopleEmails']
        new_to_ignore.refresh_from_db()
        new_to_confirm.refresh_from_db()
        assert len(people_emails) == 1
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER')
        alert = Alert.objects.filter(type=alert_type)
        assert alert.count() == 1
        mock_invite.assert_called_once()


@pytest.mark.functional(permissions=['user.delete_user'])
def test_cannot_delete_itself(graphql_client, graphql_user):
    with patch('laika.aws.cognito.cognito'):
        graphql_client.execute(DELETE_USERS, variables={'input': [graphql_user.email]})

        assert User.objects.filter(email=graphql_user.email).exists()


@pytest.mark.functional(permissions=['user.delete_user'])
def test_delete_other_users(graphql_client, graphql_user, users):
    with patch('laika.aws.cognito.cognito'):
        emails = [user.email for user in users]

        graphql_client.execute(DELETE_USERS, variables={'input': emails})

        assert not User.objects.filter(email__in=emails).exists()


CONFIRM_PEOPLE_CANDIDATE_MUTATION = '''
    mutation($confirmedPeopleCandidates: [ConfirmUserPermissionInput!],
             $ignoredPeopleEmails: [String!]) {
        confirmPeopleCandidates(
            confirmedPeopleCandidates: $confirmedPeopleCandidates,
            ignoredPeopleEmails: $ignoredPeopleEmails
        ) {
            peopleEmails
        }
    }
    '''


@pytest.mark.functional
def test_update_team_notes(graphql_client, graphql_organization, team):
    response = graphql_client.execute(
        '''
            mutation updateTeam($input: UpdateTeamInput!) {
                updateTeam(input: $input) {
                  data {
                    id
                    notes
                  }
                }
            }
        ''',
        variables={'input': {'id': str(team.id), 'notes': '<p>notes updated</p>'}},
    )

    data = dict(response['data']['updateTeam']['data'])
    notes = data['notes']
    assert notes == '<p>notes updated</p>'


@pytest.mark.functional
def test_update_team_charter(graphql_client, graphql_organization, team):
    response = graphql_client.execute(
        '''
            mutation updateTeam($input: UpdateTeamInput!) {
                updateTeam(input: $input) {
                  data {
                    id
                    charter
                  }
                }
            }
        ''',
        variables={'input': {'id': str(team.id), 'charter': '<p>charter updated</p>'}},
    )

    data = dict(response['data']['updateTeam']['data'])
    notes = data['charter']
    assert notes == '<p>charter updated</p>'


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user(graphql_client, graphql_organization, create_permission_groups):
    response = graphql_client.execute(
        INVITE_USER_TO_ORGANIZATION,
        variables={
            'input': {
                'firstName': 'Nono',
                'lastName': 'Anime',
                'showInviterName': True,
                'email': TEST_EMAIL,
                'role': 'OrganizationAdmin',
                'userPreferences': USER_PREFERENCES,
                'organizationId': str(graphql_organization.id),
                'partial': True,
            }
        },
    )
    invite_response = response['data']['inviteToOrganization']
    assert invite_response['data'] is not None
    assert invite_response['success'] is True

    response = graphql_client.execute(
        INVITE_USER_TO_ORGANIZATION,
        variables={
            'input': {
                'firstName': 'Nono',
                'lastName': 'Anime',
                'showInviterName': True,
                'email': TEST_EMAIL,
                'role': 'OrganizationAdmin',
                'userPreferences': USER_PREFERENCES,
                'organizationId': str(graphql_organization.id),
                'partial': False,
            }
        },
    )
    invite_response = response['data']['inviteToOrganization']
    assert invite_response['data'] is None
    assert invite_response['success'] is False
    assert invite_response['error']['code'] == 'user'
    assert 'Cannot invite user' in invite_response['error']['message']


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user_salesperson_with_task(graphql_client, graphql_organization):
    Group.objects.create(name='premium_sales')
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            INVITE_USER_TO_ORGANIZATION,
            variables={
                'input': {
                    'firstName': 'Nono',
                    'lastName': 'Anime',
                    'showInviterName': True,
                    'email': TEST_EMAIL,
                    'role': 'OrganizationSales',
                    'userPreferences': USER_PREFERENCES,
                    'organizationId': str(graphql_organization.id),
                    'partial': False,
                }
            },
        )
        invite_response = response['data']['inviteToOrganization']
        user = User.objects.get(email=invite_response['data']['email'])
        assert ActionItem.objects.filter(assignees=user).count() == 3
        assert invite_response['data'] is not None
        assert invite_response['success'] is True
        create_user_mock.assert_called()


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user_viewer_with_task(graphql_client, graphql_organization):
    Group.objects.create(name='premium_viewer')
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            INVITE_USER_TO_ORGANIZATION,
            variables={
                'input': {
                    'firstName': 'Nono',
                    'lastName': 'Anime',
                    'showInviterName': True,
                    'email': TEST_EMAIL,
                    'role': 'OrganizationViewer',
                    'userPreferences': USER_PREFERENCES,
                    'organizationId': str(graphql_organization.id),
                    'partial': False,
                }
            },
        )
        invite_response = response['data']['inviteToOrganization']
        user = User.objects.get(email=invite_response['data']['email'])
        assert ActionItem.objects.filter(assignees=user).count() == 1
        assert invite_response['data'] is not None
        assert invite_response['success'] is True
        create_user_mock.assert_called()


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user_viewer_and_create_policy_action_items(
    graphql_client, graphql_organization, graphql_user
):
    Group.objects.create(name='premium_viewer')

    policy = create_published_empty_policy(
        graphql_organization, graphql_user, is_required=True, is_published=True
    )
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            INVITE_USER_TO_ORGANIZATION,
            variables={
                'input': {
                    'firstName': 'Nono',
                    'lastName': 'Anime',
                    'showInviterName': True,
                    'email': TEST_EMAIL,
                    'role': 'OrganizationViewer',
                    'userPreferences': USER_PREFERENCES,
                    'organizationId': str(graphql_organization.id),
                    'partial': False,
                }
            },
        )
        invite_response = response['data']['inviteToOrganization']
        user = User.objects.get(email=invite_response['data']['email'])
        assert (
            Policy.objects.get(id=policy.id).action_items.filter(assignees=user).count()
            == 1
        )
        assert invite_response['data'] is not None
        assert invite_response['success'] is True
        create_user_mock.assert_called()


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user_viewer_without_task(
    graphql_client, graphql_organization, create_permission_groups
):
    response = graphql_client.execute(
        INVITE_USER_TO_ORGANIZATION,
        variables={
            'input': {
                'firstName': 'Nono',
                'lastName': 'Anime',
                'showInviterName': True,
                'email': TEST_EMAIL,
                'role': 'OrganizationViewer',
                'userPreferences': USER_PREFERENCES,
                'organizationId': str(graphql_organization.id),
                'partial': True,
            }
        },
    )
    invite_response = response['data']['inviteToOrganization']
    user = User.objects.get(email=invite_response['data']['email'])
    assert ActionItem.objects.filter(assignees=user).count() == 0
    assert invite_response['data'] is not None
    assert invite_response['success'] is True


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user_create_alert_with_single_match_lo_background_check(
    graphql_client, graphql_organization, graphql_user
):
    Group.objects.create(name='premium_viewer')
    laika_object, _ = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data={'First Name': 'Leo', 'Last Name': 'Messi', 'Link to People Table': None},
    )
    create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            INVITE_USER_TO_ORGANIZATION,
            variables={
                'input': {
                    'firstName': 'Leo',
                    'lastName': 'Messi',
                    'showInviterName': True,
                    'email': TEST_EMAIL,
                    'role': 'OrganizationViewer',
                    'userPreferences': USER_PREFERENCES,
                    'organizationId': str(graphql_organization.id),
                    'partial': False,
                }
            },
        )

        invite_response = response['data']['inviteToOrganization']
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER')
        alert = Alert.objects.filter(type=alert_type)
        assert alert.count() == 1
        assert invite_response['success'] is True
        create_user_mock.assert_called()


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user_create_alert_with_multiple_match_lo_background_check(
    graphql_client, graphql_organization, graphql_user
):
    Group.objects.create(name='premium_viewer')
    laika_objects, _ = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data=[
            {'First Name': 'Leo', 'Last Name': 'Messi', 'Link to People Table': None},
            {'First Name': 'Leo', 'Last Name': 'Messi', 'Link to People Table': None},
        ],
    )
    create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            INVITE_USER_TO_ORGANIZATION,
            variables={
                'input': {
                    'firstName': 'Leo',
                    'lastName': 'Messi',
                    'showInviterName': True,
                    'email': TEST_EMAIL,
                    'role': 'OrganizationViewer',
                    'userPreferences': USER_PREFERENCES,
                    'organizationId': str(graphql_organization.id),
                    'partial': False,
                }
            },
        )

        invite_response = response['data']['inviteToOrganization']
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER')
        alert = Alert.objects.filter(type=alert_type)
        assert alert.count() == 1
        assert invite_response['success'] is True
        create_user_mock.assert_called()


@pytest.mark.functional(permissions=['user.add_user'])
def test_invite_user_create_alert_multiple_match_by_email_lo_background_check(
    graphql_client, graphql_organization, graphql_user
):
    Group.objects.create(name='premium_viewer')
    laika_objects, _ = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data=[
            {'First Name': 'Leo', 'Last Name': 'Messi', 'Link to People Table': None},
            {
                'First Name': 'Cristiano',
                'Last Name': 'Ronaldo',
                'Link to People Table': None,
                'Email': TEST_EMAIL,
            },
        ],
    )
    create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            INVITE_USER_TO_ORGANIZATION,
            variables={
                'input': {
                    'firstName': 'Leo',
                    'lastName': 'Messi',
                    'showInviterName': True,
                    'email': TEST_EMAIL,
                    'role': 'OrganizationViewer',
                    'userPreferences': USER_PREFERENCES,
                    'organizationId': str(graphql_organization.id),
                    'partial': False,
                }
            },
        )

        invite_response = response['data']['inviteToOrganization']
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER')
        alert = Alert.objects.filter(type=alert_type)
        assert alert.count() == 1
        assert invite_response['success'] is True
        create_user_mock.assert_called()


@pytest.mark.functional(permissions=['user.change_user'])
def test_bulk_invite_user_create_alert_with_single_match_lo_background_check(
    graphql_client, graphql_organization, graphql_user
):
    Group.objects.create(name='premium_viewer')
    laika_objects, _ = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data=[
            {'First Name': 'Leo', 'Last Name': 'Messi', 'Link to People Table': None},
            {
                'First Name': 'Cristiano',
                'Last Name': 'Ronaldo',
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
    file_path = f'{os.path.dirname(__file__)}/resources/template_users.xlsx'
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            BULK_INVITE_USER,
            variables={
                'input': {
                    'inviteUserFile': {
                        'fileName': 'template_users.xlsx',
                        'file': file_to_base64(file_path),
                    },
                    'partial': False,
                }
            },
        )
        invite_response = response['data']['bulkInviteUser']
        upload_result = invite_response['uploadResult']
        assert 3 == upload_result[0]['successfulRows']
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER')
        alert = Alert.objects.filter(type=alert_type)
        assert alert.count() == 2
        create_user_mock.assert_called()


@pytest.mark.functional(permissions=['user.change_user'])
def test_bulk_invite_user_create_alert_with_multiple_match_lo_background_check(
    graphql_client, graphql_organization, graphql_user
):
    Group.objects.create(name='premium_viewer')
    laika_objects, _ = create_lo_with_connection_account(
        graphql_organization,
        vendor_name=CHECKR_SYSTEM,
        data=[
            {
                'First Name': 'Cristiano',
                'Last Name': 'Ronaldo',
                'Link to People Table': None,
            },
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
    file_path = f'{os.path.dirname(__file__)}/resources/template_users.xlsx'
    with patch('user.utils.invite_laika_user.create_user') as create_user_mock:
        create_user_mock.return_value = COGNITO_NEW_USER
        response = graphql_client.execute(
            BULK_INVITE_USER,
            variables={
                'input': {
                    'inviteUserFile': {
                        'fileName': 'template_users.xlsx',
                        'file': file_to_base64(file_path),
                    },
                    'partial': False,
                }
            },
        )
        invite_response = response['data']['bulkInviteUser']
        upload_result = invite_response['uploadResult']
        assert 3 == upload_result[0]['successfulRows']
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER')
        alert = Alert.objects.filter(type=alert_type)
        assert alert.count() == 1
        create_user_mock.assert_called()


@pytest.mark.functional()
def test_create_concierge_user():
    user = User.objects.create(
        email=EMAIL, user_preferences=DEFAULT_USER_PREFERENCES, username=EMAIL
    )

    concierge = Concierge(user=user)
    concierge.save()
    assert concierge


@pytest.mark.functional()
def test_add_concierge_user_to_group():
    Group.objects.create(name='concierge')

    user = User.objects.create(
        email=EMAIL, user_preferences=DEFAULT_USER_PREFERENCES, username=EMAIL
    )

    add_concierge_user_to_group(user)
    assert user.groups.get(name='concierge')


@pytest.mark.functional
@patch(
    'user.concierge_helpers.send_invite_concierge_email',
    return_value={'login_link': ORIGIN_LOCALHOST[1], 'success': True},
)
def test_send_digest_alert_email(send_invite_concierge_email_mock):
    user = User.objects.create(
        email=EMAIL, user_preferences=DEFAULT_USER_PREFERENCES, username=EMAIL
    )

    cognito_user = {'temporary_password': ''}
    response = send_concierge_user_email_invitation(user, cognito_user)
    send_invite_concierge_email_mock.assert_called_once()

    expected_login_link = LAIKA_CONCIERGE_REDIRECT or ORIGIN_LOCALHOST[1]
    assert response['login_link'] is expected_login_link
    assert response['success'] is True


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_people_incredible_filters(graphql_client, users, graphql_organization):
    user_common_data = {
        'organization': graphql_organization,
        'email': 'john@admin.com',
        'role': ROLE_ADMIN,
        'first_name': 'johnC',
        'last_name': 'doeC',
        'employment_type': 'employee',
        'employment_subtype': 'full-time',
    }

    specific_fields = {
        'first_name': ('leo', 'is', 1),
        'last_name': ('mes', 'contains', 1),
        'email': ('leo@heylaika.com', 'is', 0),
        'phone_number': ('123456789', 'contains', 1),
        'title': ('title', 'is', 1),
        'department': ('department', 'is', 1),
        'employment_type': ('manager', 'is', 1),
        'employment_subtype': ('subtype', 'is', 1),
        'background_check_status': (BACKGROUND_CHECK_STATUS_PENDING, 'is', 1),
        'manager': (users[0], 'is', 1),
    }

    i = 0
    for key, value in specific_fields.items():
        data = user_common_data.copy()
        data.update({key: value[0], 'email': f'email{i}@heylaika.com'})
        create_user(**data)
        i += 1

    for key, value in specific_fields.items():
        filter_value = value[0]
        if key == 'manager':
            filter_value = value[0].email
        response = graphql_client.execute(
            GET_USERS,
            variables={
                "filters": [{"field": key, "value": filter_value, "operator": value[1]}]
            },
        )

        collection = _get_collection_users(response)
        assert len(collection) == value[2]

    response = graphql_client.execute(
        GET_USERS,
        variables={
            "filters": [{"field": 'non_field', "value": 'no', "operator": 'is'}]
        },
    )
    collection = _get_collection_users(response)
    assert collection is None


@pytest.mark.functional(permissions=['user.view_concierge', 'user.view_user'])
def test_get_users_relation_with_lo(
    graphql_client, users, lo_users, lo_background_check
):
    lo_user1, lo_user2 = lo_users
    user = users[1]
    with patch(
        'user.utils.associate_users_with_lo.get_users_relation_with_lo',
        return_value=[
            (user.id, 'mock', lo_user1.data['Id'], lo_user1.object_type.id),
            (user.id, 'mock', lo_user2.data['Id'], lo_user1.object_type.id),
            (
                user.id,
                'mock',
                lo_background_check[0].data['Id'],
                lo_background_check[0].object_type.id,
            ),
        ],
    ) as get_users_relation_with_lo_mock:
        response = graphql_client.execute(
            GET_USERS_WITH_LO_IDS, variables={'allUsers': True}
        )
        collection = _get_collection_users(response)
        for current_user in collection:
            if current_user['email'] == user.email:
                assert json.loads(current_user['loUserIds']) == {
                    USER.type: [lo_user1.data['Id'], lo_user2.data['Id']],
                    BACKGROUND_CHECK.type: [lo_background_check[0].data['Id']],
                }
        get_users_relation_with_lo_mock.assert_called_once()


@pytest.mark.functional()
def test_get_cognito_roles_for_auditor_updating_to_auditor_admin(auditors):
    auditor, _ = auditors
    _, new_role = get_old_and_new_cognito_role(auditor, auditor.role, AUDITOR_ADMIN)
    assert new_role == AUDITOR_ADMIN


@pytest.mark.functional()
def test_get_cognito_roles_for_auditor_admin_updating_to_auditor(auditors):
    _, auditor_admin = auditors
    _, new_role = get_old_and_new_cognito_role(
        auditor_admin, auditor_admin.role, AUDITOR
    )
    assert new_role == AUDITOR


@pytest.mark.functional()
def test_get_cognito_roles_for_auditor_updating_to_organization_admin(auditors):
    auditor, _ = auditors
    _, new_role = get_old_and_new_cognito_role(auditor, auditor.role, ROLE_ADMIN)
    assert new_role == AUDITOR


@pytest.mark.functional()
def test_get_cognito_roles_for_org_admin_updating_to_organization_member(users):
    admin, _, _ = users
    _, new_role = get_old_and_new_cognito_role(admin, admin.role, ROLE_MEMBER)
    assert new_role == ROLE_MEMBER


@pytest.mark.functional()
def test_get_cognito_roles_for_org_member_updating_to_organization_admin(users):
    _, member, _ = users
    _, new_role = get_old_and_new_cognito_role(member, member.role, ROLE_ADMIN)
    assert new_role == ROLE_ADMIN


@pytest.mark.functional()
def test_get_cognito_roles_for_salesperson_updating_to_org_admin(users):
    _, _, sales = users
    _, new_role = get_old_and_new_cognito_role(sales, sales.role, ROLE_ADMIN)
    assert new_role == ROLE_ADMIN


@pytest.mark.functional(permissions=['user.add_user'])
@patch('user.mutations.manage_okta_user', return_value='Some fake okta user')
def test_resend_invitation_okta_user(manage_okta_user_mock, graphql_client, okta_user):
    response = graphql_client.execute(
        RESEND_INVITATION, variables={'email': 'john@admin.com'}
    )

    resend_invitation = response['data']['resendInvitation']['success']
    assert resend_invitation is True


@pytest.mark.functional(permissions=['user.add_user'])
@patch('user.mutations.manage_cognito_user', return_value='Some fake cognito user')
def test_resend_invitation_cognito_user(
    manage_cognito_user_mock, graphql_client, cognito_user
):
    response = graphql_client.execute(
        RESEND_INVITATION, variables={'email': 'john@admin.com'}
    )

    resend_invitation = response['data']['resendInvitation']['success']
    assert resend_invitation is True


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_concierge_partners(graphql_client, graphql_organization):
    created_partner = Partner.objects.create(name='partner_1', type=PartnerType.PENTEST)
    response = graphql_client.execute(GET_CONCIERGE_PARTNERS)
    partners = response['data']['conciergePartners']
    assert len(partners) == 1
    assert partners[0]['id'] == str(created_partner.id)


@pytest.mark.functional(permissions=['user.add_user'])
@patch('user.mutations.invite_user_m')
def test_delegate_uninvited_user_integration(
    mock_invite_user_m, user, graphql_organization, graphql_client
):
    graphql_organization.customer_success_manager_user = create_user(
        organization=graphql_organization,
        first_name='user_csm',
        last_name='user_csm',
        email="user_csm@admin",
    )
    graphql_organization.save()
    mock_invite_user_m.return_value = {'data': user, 'permissions': []}
    response = graphql_client.execute(
        DELEGATE_UNINVITED_USER_INTEGRATION,
        variables={
            "input": {
                "firstName": "johnC",
                "lastName": "doeC",
                "email": "john@admin.com",
                "category": "Dummy Category",
                "vendorId": None,
            }
        },
    )
    data = response['data']['delegateUninvitedUserIntegration']
    assert mock_invite_user_m.called
    assert data['email'] == user.email


@pytest.mark.functional(permissions=['user.add_user'])
@patch('user.mutations.send_email_with_cc', return_value=True)
def test_delegate_user_integration(
    mock_send_email_with_cc, user, graphql_organization, graphql_client
):
    graphql_organization.customer_success_manager_user = create_user(
        organization=graphql_organization,
        first_name='user_csm',
        last_name='user_csm',
        email="user_csm@admin",
    )
    graphql_organization.save()
    response = graphql_client.execute(
        DELEGATE_USER_INTEGRATION,
        variables={
            "input": {
                "email": user.email,
                "vendorId": None,
                "category": "Dummy Category",
            }
        },
    )
    data = response['data']['delegateUserIntegration']
    assert mock_send_email_with_cc.called
    assert data['email'] == user.email
