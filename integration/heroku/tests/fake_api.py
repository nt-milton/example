from pathlib import Path

from httmock import HTTMock, urlmatch

PARENT_PATH = Path(__file__).parent


def fake_heroku_api():
    return HTTMock(_fake_heroku_api)


def teams_response():
    path = PARENT_PATH / 'raw_teams_response.json'
    return open(path, 'r').read()


def users_response():
    path = PARENT_PATH / 'raw_team_members_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='api.heroku.com')
def _fake_heroku_api(url, request):
    if 'teams' in url.path:
        if 'members' in url.path:
            return users_response()

        return teams_response()

    raise ValueError('Unexpected operation for Heroku fake api')
