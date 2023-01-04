import pathlib

from integration.token import _token_requires_renew


def test_expired_token():
    with open(pathlib.Path(__file__).parent / 'expired_token.txt', 'r') as file:
        expired_token = file.read()
        assert _token_requires_renew(expired_token)


def test_invalid_token():
    assert _token_requires_renew('invalid token')
