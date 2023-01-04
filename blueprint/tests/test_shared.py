from unittest.mock import patch

import pytest

from blueprint.admin.shared import get_framework_tag_records, get_roles_records
from blueprint.choices import BlueprintPage
from blueprint.models import Page
from blueprint.tests.test_commons import AIRTABLE_API_KEY_TEST, AIRTABLE_BASE_ID


class MockRequest(object):
    def __init__(self, user=None):
        self.user = user


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[{'id': '123a', 'fields': {'Name': 'Any Name'}}],
)
def test_get_framework_tag_records(execute_airtable_request_mock, graphql_user):
    Page.objects.create(
        name=str(BlueprintPage.CERTIFICATION),
        airtable_api_key=AIRTABLE_API_KEY_TEST,
        airtable_link=AIRTABLE_BASE_ID,
    )

    tags = get_framework_tag_records(MockRequest(user=graphql_user))
    execute_airtable_request_mock.assert_called_once()
    assert tags.get('123a', {}).get('Name') == 'Any Name'


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[{'id': '123role', 'fields': {'Name': 'Technical'}}],
)
def test_get_roles_records(execute_airtable_request_mock, graphql_user):
    Page.objects.create(
        name=str(BlueprintPage.CONTROLS),
        airtable_api_key=AIRTABLE_API_KEY_TEST,
        airtable_link=AIRTABLE_BASE_ID,
    )

    roles = get_roles_records(MockRequest(user=graphql_user))
    execute_airtable_request_mock.assert_called_once()
    assert roles.get('123role', {}).get('Name') == 'Technical'
