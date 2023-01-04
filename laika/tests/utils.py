import base64
from typing import List

from django.db.models import Q
from httmock import HTTMock, all_requests, response
from jwt import decode


def mock_responses(responses=None, status_code=None):
    if responses is None:
        responses = []
    results = list(reversed(responses))

    @all_requests
    def next_response(url, request):
        result = results.pop()
        return (
            response(status_code=status_code, content=result) if status_code else result
        )

    return HTTMock(next_response)


def mock_responses_with_status(responses: List[response] = None):
    if responses is None:
        responses = []
    results = list(reversed(responses))

    @all_requests
    def next_response(url, request):
        return results.pop()

    return HTTMock(next_response)


def decode_without_verify_exp(user_jwt, **kwargs):
    return decode(
        user_jwt, **{**kwargs, 'options': {'verify_aud': False, 'verify_exp': False}}
    )


def file_to_base64(file_path=None):
    if file_path is None:
        raise ValueError('The file_path should not be None')
    file = open(file_path, 'rb').read()
    return base64.b64encode(file).decode('UTF-8')


def q_mock_translate(source, target):
    def translator(**kwargs):
        if source in kwargs:
            return Q(**{target: kwargs[source]})
        return Q(**kwargs)

    return translator
