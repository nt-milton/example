import json

import pytest

from integration.github_apps.implementation import (
    GITHUB_SYSTEM,
    map_pull_requests_to_laika_object,
    map_users_to_laika_object,
)
from integration.github_apps.mapper import PullRequestRecord

LAIKA_APP = 'laika-app'
PR_VISIBILITY = 'Private'
PR_NUMBER = 565
PR_KEY = f'{LAIKA_APP}-{PR_NUMBER}'
REPORTER = 'USER_1'
DEVELOP = 'develop'
FEATURE = 'feature/LK-2737'
MERGED = 'MERGED'
TITLE = 'LK-2737 Tech Debt run pytest for pull request'
LINK = 'https://github.com/heylaika/laika-app/pull/565'
CREATED_ON = '2020-10-25T14:44:19Z'
UPDATED_ON = '2020-10-26T14:44:19Z'
GITHUB_ORG = 'heylaika'
CONNECTION_NAME = 'my-account'

USER = "kenneth"
EMAIL = "email@test.com"
ID = "MDXNlcjczODE5Q=="


@pytest.fixture
def pr_payload():
    return json.loads(PR_PAYLOAD)


@pytest.fixture
def pr2_payload():
    return json.loads(PR2_PAYLOAD)


@pytest.fixture
def user_payload():
    return json.loads(USER_PAYLOAD)


def test_pull_request_laika_object_mapping(pr_payload):
    assert_payload_mapping(pr_payload)


def test_pull_request_laika_object_mapping_with_reviews(pr2_payload):
    assert_payload_mapping(pr2_payload)


def assert_payload_mapping(payload):
    github_record = PullRequestRecord(GITHUB_ORG, LAIKA_APP, payload, PR_VISIBILITY)
    laika_object = map_pull_requests_to_laika_object(github_record, CONNECTION_NAME)
    expected = {
        'Key': PR_KEY,
        'Repository': LAIKA_APP,
        'Repository Visibility': PR_VISIBILITY,
        'Target': DEVELOP,
        'Source': FEATURE,
        'State': MERGED,
        'Title': TITLE,
        'Is Verified': True,
        'Is Approved': True,
        'Approvers': 'dmgamboav,kennethads',
        'Url': LINK,
        'Reporter': REPORTER,
        'Created On': CREATED_ON,
        'Updated On': UPDATED_ON,
        'Organization': GITHUB_ORG,
        'Source System': GITHUB_SYSTEM,
        'Connection Name': CONNECTION_NAME,
    }
    assert laika_object == expected


def test_user_laika_object_mapping(user_payload):
    users_record = user_payload
    laika_object = map_users_to_laika_object(users_record, CONNECTION_NAME)
    expected = {
        'Id': ID,
        'First Name': USER,
        'Last Name': "",
        'Email': EMAIL,
        'Is Admin': True,
        'Title': "kennethads",
        'Organization Name': GITHUB_ORG,
        'Roles': 'Admin',
        'Groups': '',
        'Mfa Enabled': False,
        'Mfa Enforced': '',
        'Source System': GITHUB_SYSTEM,
        'Connection Name': CONNECTION_NAME,
    }
    assert laika_object == expected


def test_laika_object_mapping_empty_reporter_for_missing_author(pr_payload):
    pr_payload.pop('author')
    github_record = PullRequestRecord(GITHUB_ORG, LAIKA_APP, pr_payload, PR_VISIBILITY)
    lo = map_pull_requests_to_laika_object(github_record, CONNECTION_NAME)
    expected = {'Reporter': None}
    assert expected.items() < lo.items()


PR_PAYLOAD = f'''
{{
  "number": "{PR_NUMBER}",
  "weblink": "{LINK}",
  "title": "{TITLE}",
  "target": "{DEVELOP}",
  "source": "{FEATURE}",
  "state": "{MERGED}",
  "reviewDecision": "APPROVED",
  "reviews": {{
    "nodes": [
      {{
        "state": "APPROVED",
        "author": {{
          "login": "kennethads"
        }}
      }},
      {{
        "state": "APPROVED",
        "author": {{
          "login": "dmgamboav"
        }}
      }},
      {{
        "state": "APPROVED",
        "author": {{
          "login": "kennethads"
        }}
      }}
    ]
  }},
  "author": {{
    "login": "{REPORTER}"
  }},
  "createdAt": "{CREATED_ON}",
  "updatedAt": "{UPDATED_ON}"
}}
'''

PR2_PAYLOAD = f'''
{{
  "number": "{PR_NUMBER}",
  "weblink": "{LINK}",
  "title": "{TITLE}",
  "target": "{DEVELOP}",
  "source": "{FEATURE}",
  "state": "{MERGED}",
  "reviewDecision": null,
  "reviews": {{
    "nodes": [
      {{
        "state": "APPROVED",
        "author": {{
          "login": "kennethads"
        }}
      }},
      {{
        "state": "APPROVED",
        "author": {{
          "login": "dmgamboav"
        }}
      }},
      {{
        "state": "APPROVED",
        "author": {{
          "login": "kennethads"
        }}
      }}
    ]
  }},
  "author": {{
    "login": "{REPORTER}"
  }},
  "createdAt": "{CREATED_ON}",
  "updatedAt": "{UPDATED_ON}"
}}
'''

USER_PAYLOAD = f'''
{{
  "role": "ADMIN",
  "id": "{ID}",
  "name": "{USER}",
  "email": "{EMAIL}",
  "login": "kennethads",
  "organization_name": "{GITHUB_ORG}",
  "title": "kennethads"
}}
'''
