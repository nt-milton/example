from integration.bitbucket import rest_client


def test_get_url_with_privacy_filter_query():
    slug = 'bitbucket_test'
    result = rest_client._get_url_with_privacy_filter_query(
        f'{rest_client.API_URL}/repositories/{slug}', ['PRIVATE']
    )
    expected_url = f'{rest_client.API_URL}/repositories/{slug}'
    assert result == f'{expected_url}?q=is_private=true'


def test_get_url_with_public_filter_query():
    slug = 'bitbucket_test'
    result = rest_client._get_url_with_privacy_filter_query(
        f'{rest_client.API_URL}/repositories/{slug}', ['PUBLIC']
    )
    expected_url = f'{rest_client.API_URL}/repositories/{slug}'
    assert result == f'{expected_url}?q=is_private=false'


def test_get_url_with_public_and_private_filter_query():
    slug = 'bitbucket_test'
    result = rest_client._get_url_with_privacy_filter_query(
        f'{rest_client.API_URL}/repositories/{slug}', ['PUBLIC', 'PRIVATE']
    )
    assert result == f'{rest_client.API_URL}/repositories/{slug}'


def test_get_url_with_selected_time_range():
    result = rest_client._apply_query_to_pull_request_url(
        f'{rest_client.API_URL}/repositories/dev_heylaika/test_repository/pullrequests',
        '2020-10-06',
    )
    expected_url = (
        f'{rest_client.API_URL}/repositories/'
        'dev_heylaika/test_repository/pullrequests'
        '?q=(state="MERGED" OR state="OPEN" OR state="DECLINED") '
        'AND created_on >= 2020-10-06'
    )
    assert result == expected_url
