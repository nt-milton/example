import json
from pathlib import Path

import pytest

from integration.slack.mapper import map_users_to_laika_object


def load_response(filename):
    with open(Path(__file__).parent / filename, 'r') as file:
        return json.load(file)


@pytest.fixture
def user_list():
    response = load_response('raw_users_response.json')
    return response.get('members')


@pytest.fixture
def normal_user(user_list):
    return user_list[2]


@pytest.fixture
def bot_user_without_first_name(user_list):
    return user_list[0]


@pytest.fixture
def bot_user_with_first_name(user_list):
    return user_list[1]


CONNECTION_NAME = 'Test Connection'
FIRST_NAME = 'First Name'
LAST_NAME = 'Last Name'
EMAIL = 'Email'


def test_map_users(normal_user):
    user = map_users_to_laika_object(normal_user, CONNECTION_NAME)
    assert user.get(FIRST_NAME) == 'Laurens'
    assert user.get(LAST_NAME) == 'Ortiz'
    assert user.get(EMAIL) == 'laurens.ortiz@heylaika.com'


def test_map_bot_with_name(bot_user_with_first_name):
    user = map_users_to_laika_object(bot_user_with_first_name, CONNECTION_NAME)
    assert user.get(FIRST_NAME) == 'slackbot'
    assert user.get(LAST_NAME) == ''
    assert user.get(EMAIL) == ''


def test_map_bot_without_name(bot_user_without_first_name):
    user = map_users_to_laika_object(bot_user_without_first_name, CONNECTION_NAME)
    assert user.get(FIRST_NAME) == 'Easy Poll'
    assert user.get(LAST_NAME) == ''
    assert user.get(EMAIL) == ''
