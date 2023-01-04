from unittest.mock import patch

import pytest
from django.test import Client

from organization.tests.factory import create_organization
from user.constants import ACTIVE
from user.models import User

from .factory import create_published_empty_policy

EXPORT_DOCUMENT_BYTES_PATH = 'policy.views.export_document_bytes'
GET_USER_FROM_TOKEN_PATH = 'laika.auth.get_user_from_token'


@pytest.fixture(name='_http_client')
def http_client():
    return Client()


@pytest.fixture(name='_my_compliance_organization')
def my_compliance_organization():
    return create_organization(name='Test Organization', state=ACTIVE)


@pytest.fixture(name='_my_compliance_user')
def fixture_my_compliance_user(_my_compliance_organization):
    user = User.objects.create(
        username='Jose',
        role='OrganizationAdmin',
        organization=_my_compliance_organization,
    )
    return user


@pytest.mark.django_db
@patch(EXPORT_DOCUMENT_BYTES_PATH)
@patch(GET_USER_FROM_TOKEN_PATH)
def test_get_published_pdf_file(
    export_document_bytes,
    get_user_from_token,
    _my_compliance_organization,
    _my_compliance_user,
    _http_client,
):
    get_user_from_token.return_value = _my_compliance_user
    published_policy = create_published_empty_policy(
        _my_compliance_organization, _my_compliance_user
    )

    response = _http_client.get(f'/policy/{published_policy.id}/published')

    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/pdf'
