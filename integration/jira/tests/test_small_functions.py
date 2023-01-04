from urllib.parse import parse_qs, urlparse

from integration.jira.rest_client import generate_url
from integration.settings import ATLASSIAN_API_URL


def test_jira_url():
    cloud_id = 'asd'
    url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/api/2/search'
    order_by = 'order by updated DESC'
    jql = f'project in ("AB") AND updatedDate >= "2020-06-01" {order_by}'
    expected_url = f'{url}?expand=changelog&jql={jql}&maxResults=100&startAt=0'
    expected_url = urlparse(expected_url)
    expected_query = parse_qs(expected_url.query)
    url = generate_url(cloud_id, jira_projects=['AB'], date_range_filter='2020-06-01')
    parsed_url = urlparse(url)
    parsed_query = parse_qs(parsed_url.query)
    assert parsed_url.netloc == expected_url.netloc
    assert len(parsed_query) == len(expected_query)
    assert parsed_query.get('expand') == expected_query.get('expand')
    assert parsed_query.get('jql') == expected_query.get('jql')
    assert parsed_query.get('maxResults') == expected_query.get('maxResults')
    assert parsed_query.get('startAt') == expected_query.get('startAt')


def test_jira_url_with_fields():
    cloud_id = 'asd'
    url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/api/2/search'
    order_by = 'order by updated DESC'
    jql = f'project in ("AB") AND updatedDate >= "2020-06-01" {order_by}'
    expected_url = f'{url}?jql={jql}&maxResults=100&startAt=0'
    expected_url = f'{expected_url}&fields=key,updated'
    expected_url = urlparse(expected_url)
    expected_query = parse_qs(expected_url.query)
    url = generate_url(
        cloud_id,
        jira_projects=['AB'],
        date_range_filter='2020-06-01',
        fields=['key', 'updated'],
    )
    parsed_url = urlparse(url)
    parsed_query = parse_qs(parsed_url.query)
    assert parsed_url.netloc == expected_url.netloc
    assert len(parsed_query) == len(expected_query)
    assert parsed_query.get('expand') == expected_query.get('expand')
    assert parsed_query.get('jql') == expected_query.get('jql')
    assert parsed_query.get('maxResults') == expected_query.get('maxResults')
    assert parsed_query.get('startAt') == expected_query.get('startAt')
    assert parsed_query.get('fields') == expected_query.get('fields')
