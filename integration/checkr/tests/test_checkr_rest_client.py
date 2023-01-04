from integration.checkr.constants import CHECKR_ENDPOINTS
from integration.checkr.rest_client import (
    create_candidates,
    fetch_auth_token,
    get_account_details,
    get_nodes,
    list_candidates,
    list_invitations,
    send_invitation,
)
from integration.checkr.tests.fake_api.fake_api import fake_checkr_api
from integration.encryption_utils import encrypt_value

AUTH_TOKEN = encrypt_value('random_code')


def test_fetch_auth_token():
    with fake_checkr_api():
        response = fetch_auth_token('random_code')
    assert response is not None
    assert response['access_token'] is not None
    assert response['scope'] is not None
    assert response['checkr_account_id'] is not None


def test_list_invitations():
    with fake_checkr_api(51):
        invitations = list_invitations(AUTH_TOKEN)

    assert invitations.get('data')[0].get('id') == '0dbc204b630822161657c8c7'


def test_list_candidates():
    with fake_checkr_api(51):
        candidates = list_candidates(AUTH_TOKEN, **{'include': 'reports'})
        candidates = list(candidates)

    assert len(candidates) == 51


def test_get_account_details():
    with fake_checkr_api():
        url = CHECKR_ENDPOINTS.get('account_details', {}).get('url')
        account_details = get_account_details(AUTH_TOKEN, url)

    assert isinstance(account_details['company'], dict)


def test_get_nodes():
    with fake_checkr_api():
        url = CHECKR_ENDPOINTS.get('list_nodes', {}).get('url')
        nodes = get_nodes(AUTH_TOKEN, url)
    assert nodes['data'][0]['custom_id'] == '12345'


def test_get_packages():
    with fake_checkr_api():
        url = CHECKR_ENDPOINTS.get('list_packages', {}).get('url')
        packages = get_nodes(AUTH_TOKEN, url)
    assert packages[0]['id'] == 'b59c68e55d4d8a9b6e7482d7'


def test_create_candidates():
    with fake_checkr_api():
        candidate = create_candidates(
            AUTH_TOKEN, 'candidates', **{'data': {'email': 'tom+test1@heylaika.com'}}
        )

    assert isinstance(candidate['id'], str)


def test_send_invitation():
    with fake_checkr_api():
        invitation = send_invitation(
            AUTH_TOKEN,
            'invitations',
            **{
                'data': {
                    "candidate_id": "fb38dafd08f3208d61927b5d",
                    "package": "laika_driver_standard",
                    "work_locations": [{"state": "AL", "city": "Birmingham"}],
                }
            }
        )

    assert invitation['candidate_id'] == 'fb38dafd08f3208d61927b5d'
