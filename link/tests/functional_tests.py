import logging

import pytest
from django.test import Client
from requests import exceptions

from laika.utils.dates import YYYY_MM_DD_HH_MM_SS as DATE_FORMAT
from laika.utils.dates import str_date_to_date_formatted
from link.models import Link
from link.proxy import proxy_url_request
from organization.tests import create_organization
from report.tests import create_report, create_template
from user.tests import create_user

from .mutations import UPDATE_LINK

TEXT_HTML_CONTENT_TYPE = 'text/html; charset=utf-8'
INVALID_LINK = 'This link is invalid!'

http_client = Client()
LOGGER = logging.getLogger(__name__)


def post(*args, **kwargs):
    raise exceptions.Timeout()


@pytest.fixture
def organization():
    return create_organization(name='laika-dev')


@pytest.fixture()
def user(organization):
    return create_user(organization, [], 'laika@heylaika.com')


@pytest.fixture()
def template(organization):
    return create_template(organization=organization)


@pytest.fixture()
def html_template(organization):
    return create_template(organization=organization, name='Reports Template.html')


@pytest.fixture()
def invalid_template(organization):
    template = create_template(organization=organization)
    template.name = 'Invalid template'
    template.save()


@pytest.fixture
def valid_report(organization, user):
    report = create_report(organization, name='report-test', owner=user)
    report.link.url = f'/report/{report.id}?token={report.token}'
    report.link.is_enabled = True
    report.link.save()
    return report


@pytest.fixture
def invalid_report(organization, user):
    report = create_report(organization, name='report-test', owner=user)
    report.link.url = f'/report/{report.id}?token={report.token}'
    report.link.save()
    return report


@pytest.fixture
def expired_report(organization, user):
    report = create_report(organization, name='report-test', owner=user)
    report.link.expiration_date = str_date_to_date_formatted(
        '2020-01-01 00:00:00', DATE_FORMAT
    )
    report.link.url = f'/report/{report.id}?token={report.token}'
    report.link.save()
    return report


@pytest.fixture
def disabled_link_report(organization, user):
    report = create_report(organization, name='report-test', owner=user)
    report.link.expiration_date = None
    report.link.is_enabled = False
    report.link.url = f'/report/{report.id}?token={report.token}'
    report.link.save()
    return report


@pytest.fixture
def invalid_token_internal_url_report(organization, user):
    report = create_report(organization, name='report-test', owner=user)
    report.link.url = f'/report/{report.id}'
    report.link.save()
    return report


@pytest.mark.functional
def test_valid_report_public_link(valid_report):
    assert (
        f'report/{valid_report.id}?token={valid_report.token}' in valid_report.link.url
    )
    assert 'link' in valid_report.link.public_url
    assert valid_report.link.is_valid


@pytest.mark.functional
def test_invalid_report_public_link(invalid_report):
    assert (
        f'report/{invalid_report.id}?token={invalid_report.token}'
        in invalid_report.link.url
    )
    assert 'link' in invalid_report.link.public_url
    assert not invalid_report.link.is_valid


@pytest.mark.functional
def test_redirect_with_public_link(valid_report, template):
    response = proxy_url_request(None, valid_report.link.id, http_client)
    assert response.status_code == 200
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE


@pytest.mark.functional
def test_expired_public_link(expired_report, template):
    response = proxy_url_request(None, expired_report.link.id, http_client)
    decoded_content = response.content.decode('utf-8')
    assert response.status_code == 200
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE
    assert 'This link is expired!' in decoded_content


@pytest.mark.functional
def test_disabled_public_link(disabled_link_report, template):
    response = proxy_url_request(None, disabled_link_report.link.id, http_client)
    decoded_content = response.content.decode('utf-8')
    assert response.status_code == 404
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE
    assert INVALID_LINK in decoded_content


@pytest.mark.functional
def test_not_found_public_link():
    response = proxy_url_request(
        None, '533776ed-904f-4b19-8e07-cb11db6d4033', http_client
    )
    decoded_content = response.content.decode('utf-8')
    assert response.status_code == 404
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE
    assert INVALID_LINK in decoded_content


@pytest.mark.functional
def test_invalid_uuid_public_link():
    response = http_client.get('/link/123/')
    decoded_content = response.content.decode('utf-8')
    assert response.status_code == 404
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE
    assert INVALID_LINK in decoded_content


@pytest.mark.functional
def test_html_template_with_public_link(valid_report, html_template):
    response = proxy_url_request(None, valid_report.link.id, http_client)
    assert response.status_code == 200
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE


@pytest.mark.functional
def test_invalid_internal_token_public_link(
    invalid_token_internal_url_report, template
):
    response = proxy_url_request(
        None, invalid_token_internal_url_report.link.id, http_client
    )
    decoded_content = response.content.decode('utf-8')
    assert response.status_code == 404
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE
    assert INVALID_LINK in decoded_content


@pytest.mark.functional(permissions=['link.change_link'])
def test_update_link(graphql_client, valid_report):
    organization, _ = graphql_client.context.values()
    link_id = valid_report.link.id
    valid_report.link.organization = organization
    valid_report.link.save()
    variables = {
        'input': {'linkId': str(link_id), 'timeZone': 'utc', 'isEnabled': True}
    }

    graphql_client.execute(UPDATE_LINK, variables=variables)
    updated_link = Link.objects.get(id=link_id)

    assert updated_link.is_enabled is True
    assert updated_link.time_zone == 'utc'
    assert not updated_link.expiration_date


@pytest.mark.functional
def test_proxy_url_request_timeout(valid_report, template):
    http_client.post = post
    response = proxy_url_request(None, valid_report.link.id, http_client)
    decoded_content = response.content.decode('utf-8')
    assert response.status_code == 404
    assert response['Content-Type'] == TEXT_HTML_CONTENT_TYPE
    assert 'Your request timed out.' in decoded_content
