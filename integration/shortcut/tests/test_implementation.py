import json

from integration.shortcut.implementation import filter_deactivated_users
from integration.shortcut.tests.functional_tests import load_response


def test_filter():
    users = json.loads(load_response('raw_users_response.json'))
    filtered_users = filter_deactivated_users(users)
    assert len(filtered_users) == 1
