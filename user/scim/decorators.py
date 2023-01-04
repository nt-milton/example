import json
import logging

from django.core.validators import validate_email
from django.http import HttpResponseBadRequest

logger = logging.getLogger('scim')

HTTP_METHODS_WITH_REQUIRED_VALIDATION = ['POST', 'PUT', 'PATCH']


def validate_request(method, request_body):
    try:
        if method == 'PATCH':
            if request_body['operations']:
                return True
        else:
            if (
                request_body['emails'][0]['value']
                and request_body['name']['givenName']
                and request_body['name']['familyName']
                and request_body['externalId']
            ):
                try:
                    validate_email(request_body['emails'][0]['value'])
                    return True
                except Exception as e:
                    raise ValueError(e)
            return False
    except Exception as e:
        raise ValueError(e)


def has_to_validate(method):
    return method in HTTP_METHODS_WITH_REQUIRED_VALIDATION


def scim_request(func):
    def wrapper(*args, **kwargs):
        request = args[0]
        if has_to_validate(request.method):
            body = json.loads(request.body)
            try:
                if validate_request(request.method, body):
                    return func(*args, **kwargs)
                else:
                    logger.warning('Error validating email in SCIM request')
                    return HttpResponseBadRequest('Invalid request')
            except Exception as e:
                logger.warning(f'Error validating email in SCIM request: {e}')
                return HttpResponseBadRequest('Invalid request')
        else:
            return func(*args, **kwargs)

    return wrapper
