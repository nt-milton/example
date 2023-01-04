import json
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from httmock import HTTMock, response, urlmatch

EVENTS_URL = '/api/0/issues/01/events/'

TEST_DIR = Path(__file__).parent


def fake_sentry_api():
    return HTTMock(_fake_sentry_resources_api)


def fake_sentry_api_missing_credential():
    return HTTMock(_fake_auth_response_without_api_key)


@urlmatch(netloc=r'sentry.io', path='/api/0')
def _fake_sentry_resources_api(url, request):
    if 'combined-rules' in url.path:
        return monitor_response(url.path)
    if 'organizations' in url.path:
        if 'users' in url.path:
            return users_response()
        if 'projects' in url.path:
            return projects_by_org_response()
        return organizations_response()
    if 'events' in url.path:
        return events_response(url)
    if 'api/0' in url.path:
        return default_response()
    raise ValueError('Unexpected operation for sentry fake api')


def organizations_response():
    path = TEST_DIR / 'raw_organizations_response.json'
    return open(path, 'r').read()


def users_response():
    path = TEST_DIR / 'raw_user_response.json'
    return open(path, 'r').read()


def monitor_response(url_path):
    if 'project_1' in url_path:
        path = TEST_DIR / 'raw_monitor_project_1_response.json'
        return open(path, 'r').read()
    if 'project_2' in url_path:
        path = TEST_DIR / 'raw_monitor_project_2_response.json'
        return open(path, 'r').read()
    else:
        path = TEST_DIR / 'raw_monitor_project_3_response.json'
        return open(path, 'r').read()


def projects_response():
    path = TEST_DIR / 'raw_projects_response.json'
    return open(path, 'r').read()


def projects_by_org_response():
    path = TEST_DIR / 'raw_projects_by_org_response.json'
    return open(path, 'r').read()


def _mock_events_created_date(url, events):
    if EVENTS_URL in url.path:
        if '&cursor=0:15:0' in url.query:
            for event in events:
                if event.get('id') in ['17', '18']:
                    event['dateCreated'] = str(
                        datetime.now() - relativedelta(months=19)
                    )
                else:
                    event['dateCreated'] = str(datetime.now() - relativedelta(months=3))
        else:
            for event in events:
                event['dateCreated'] = str(datetime.now() - relativedelta(months=1))


def events_response(url):
    merged_headers = {}
    headers = {'Content-Type': 'application/json'}
    if EVENTS_URL in url.path and not url.query:
        path = TEST_DIR / 'raw_events_project_1_chunk_1_response.json'
        link = (
            '<https://sentry.io/api/0/issues/01/events/?&cursor=0:0:1>;'
            ' rel="previous"; results="false"; cursor="0:0:1", '
            '<https://sentry.io/api/0/issues/01/events/?&cursor=0:5:0>;'
            ' rel="next"; results="true"; cursor="0:5:0"'
        )
        merged_headers = {**dict(link=link), **headers}
    elif EVENTS_URL in url.path and '&cursor=0:5:0' in url.query:
        path = TEST_DIR / 'raw_events_project_1_chunk_2_response.json'
        link = (
            '<https://sentry.io/api/0/issues/01/events/?&cursor=0:5:1>;'
            ' rel="previous"; results="true"; cursor="0:5:1", '
            '<https://sentry.io/api/0/issues/01/events/?&cursor=0:10:0>;'
            ' rel="next"; results="true"; cursor="0:10:0"'
        )
        merged_headers = {**dict(link=link), **headers}
    elif EVENTS_URL in url.path and '&cursor=0:10:0' in url.query:
        path = TEST_DIR / 'raw_events_project_1_chunk_3_response.json'
        link = (
            '<https://sentry.io/api/0/issues/01/events/?&cursor=0:10:1>;'
            ' rel="previous"; results="true"; cursor="0:10:1", '
            '<https://sentry.io/api/0/issues/01/events/?&cursor=0:15:0>;'
            ' rel="next"; results="true"; cursor="0:15:0"'
        )
        merged_headers = {**dict(link=link), **headers}
    elif EVENTS_URL in url.path and '&cursor=0:15:0' in url.query:
        path = TEST_DIR / 'raw_events_project_1_chunk_4_response.json'
        link = (
            '<https://sentry.io/api/0/issues/01/events/?&cursor=0:15:1>;'
            ' rel="previous"; results="true"; cursor="0:15:1", '
            '<https://sentry.io/api/0/issues/01/events/>;'
            ' rel="next"; results="false"; cursor="0:0:0"'
        )
        merged_headers = {**dict(link=link), **headers}
    elif '/api/0/issues/03/events/' in url.path and not url.query:
        path = TEST_DIR / 'raw_events_project_3_response.json'
        error_response = json.loads(open(path, 'r').read())
        return response(404, error_response, headers)
    else:
        path = TEST_DIR / 'raw_events_project_2_response.json'

    events = json.loads(open(path, 'r').read())
    _mock_events_created_date(url, events)
    return response(200, events, merged_headers)


def default_response():
    path = TEST_DIR / 'raw_default_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='api.sentry.co')
def _fake_auth_response_without_api_key(url, request):
    path = TEST_DIR / 'raw_missing_authorization.json'
    api_response = open(path, 'r').read()
    headers = {'Content-Type': 'application/json'}
    return response(401, api_response, headers)
