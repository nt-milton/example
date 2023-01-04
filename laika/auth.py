import functools
import logging
import re
from typing import Optional, Union

import jwt
from django.contrib import auth
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

from laika.backends.audits_backend import AuditAuthenticationBackend
from laika.backends.base import decode_api_token, parse_api_token
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.constants import REQUEST_OPERATION_KEY
from laika.settings import CORS_ORIGIN_REGEX_WHITELIST, LOGIN_API_KEY
from laika.utils.exceptions import HandledException, ServiceException
from user.models import User as USER_MODEL

logger = logging.getLogger(__name__)


def api_key(graphql_resolver):
    @functools.wraps(graphql_resolver)
    def decorator(*args, **kwargs):
        context = args[0] if len(args) == 1 else args[1].context

        logger.info(f'Api Key Request Context: {context}. Headers: {context.headers}')

        request_origin = context.headers.get('Origin')
        cors_regex_list = '%s' % '|'.join(CORS_ORIGIN_REGEX_WHITELIST)
        if not re.match(cors_regex_list, request_origin):
            logger.exception('Some invalid origin is trying to get data from')
            raise ServiceException('Invalid request')

        if context.headers.get('Authorization') != LOGIN_API_KEY:
            logger.warning('Invalid API Key')
            raise ServiceException('Invalid API key')

        operation = f'operation: {graphql_resolver.__qualname__}'
        setattr(context, REQUEST_OPERATION_KEY, operation)

        try:
            logger.info(f'START Auth Decorator on Global Api Key for {operation}')
            response = graphql_resolver(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            raise ServiceException(e)

        return response

    return decorator


def login_required(graphql_resolver):
    @functools.wraps(graphql_resolver)
    def decorator(*args, **kwargs):
        return base_auth_decorator(
            None, AuthenticationBackend.BACKEND, graphql_resolver, *args, **kwargs
        )

    return decorator


def auditor_required(graphql_resolver):
    @functools.wraps(graphql_resolver)
    def decorator(*args, **kwargs):
        return base_auth_decorator(
            None, AuditAuthenticationBackend.BACKEND, graphql_resolver, *args, **kwargs
        )

    return decorator


def concierge_required(graphql_resolver):
    @functools.wraps(graphql_resolver)
    def decorator(*args, **kwargs):
        return base_auth_decorator(
            None,
            ConciergeAuthenticationBackend.BACKEND,
            graphql_resolver,
            *args,
            **kwargs,
        )

    return decorator


def get_authenticated_user(backend, *args) -> Optional[USER_MODEL]:
    context = args[0] if len(args) == 1 else args[1].context
    token = context.headers.get('Authorization')

    if not token or token == 'undefined' or token == 'null':
        return None

    return auth.authenticate(
        context, token=token, verify_exp=True, expected_backend=backend
    )


def some_login_required(allowed_backends):
    def some_login_required_dec(graphql_resolver):
        @functools.wraps(graphql_resolver)
        def decorator(*args, **kwargs):
            for allowed_backend in allowed_backends:
                try:
                    user = get_authenticated_user(allowed_backend.get('backend'), *args)

                    if not user:
                        continue

                    if user.is_missing_mfa():
                        raise PermissionDenied('MFA required')

                    if not user.has_perm(allowed_backend.get('permission')):
                        raise PermissionDenied(
                            'User does not have permission to '
                            f'{graphql_resolver.__name__}'
                        )

                    return base_auth_decorator(
                        user,
                        allowed_backend.get('backend'),
                        graphql_resolver,
                        *args,
                        **kwargs,
                    )
                except Exception as error:
                    logger.warning(f'Error: {error}')
                    raise ServiceException(error)

            return Exception('Unauthorized')

        return decorator

    return some_login_required_dec


def permission_required(permission, raise_exception=True):
    def permission_required_dec(graphql_resolver):
        @functools.wraps(graphql_resolver)
        def decorator(*args, **kwargs):
            context = args[0] if len(args) == 1 else args[1].context
            if context.user.is_missing_mfa():
                raise PermissionDenied('MFA required')
            if context.user.has_perm(permission):
                response = graphql_resolver(*args, **kwargs)
                return response
            if raise_exception:
                raise PermissionDenied

        return decorator

    return permission_required_dec


def base_auth_decorator(user, backend, graphql_resolver, *args, **kwargs):
    operation = f'{graphql_resolver.__qualname__}'
    context = args[0] if len(args) == 1 else args[1].context
    logger.info(
        'starting request '
        f'decorator: {backend}, '
        f'operation: {operation}, '
        f'user_agent: "{context.META.get("HTTP_USER_AGENT")}", '
        f'origin: "{context.META.get("HTTP_ORIGIN")}", '
        f'remote_host: "{context.META.get("REMOTE_HOST")}", '
        f'request_method: "{context.META.get("REQUEST_METHOD")}", '
        f'authorization: "{context.META.get("HTTP_AUTHORIZATION")}"'
    )

    if not user:
        token = context.headers.get('Authorization')
        user = get_user_from_token(token, context, backend)

    # Validate user has access to this decorator

    if not user:
        raise ServiceException('Unauthorized user 🚫')

    log_operation = f'starting operation {operation}, '
    log_username = f'username: {user.username}, '
    log_organization = ''

    try:
        if hasattr(context, 'user'):
            context.user = user
        setattr(context, REQUEST_OPERATION_KEY, operation)

        if backend == AuthenticationBackend.BACKEND:
            organization_id = user.organization.id if user.organization else 'admin'

            log_organization = f'organization: {organization_id}'

        logger.info(log_operation + log_username + log_organization)

        response = graphql_resolver(*args, **kwargs)
    except HandledException as e:
        raise ServiceException(e)
    except Exception as e:
        logger.exception(e)
        raise ServiceException(e)
    finally:
        logger.info(f'END auth decorator on {backend}')

    return response


def get_user_from_token(
    token: Union[str, bytes], context, backend
) -> Optional[USER_MODEL]:
    user = None
    if not token or token == 'undefined' or token == 'null':
        raise ServiceException('Token Expired 🚫')
    is_api_token, api_token = parse_api_token(token)
    if is_api_token:
        try:
            payload = decode_api_token(api_token)
            user_email = payload.get('email', '')
            user = USER_MODEL.objects.get(email=user_email)
        except jwt.ExpiredSignatureError:
            raise ServiceException('API Token Expired 🚫')
        except ObjectDoesNotExist:
            raise ServiceException('API User Does Not Exist 🚫')
    else:
        user = auth.authenticate(
            context, token=token, verify_exp=True, expected_backend=backend
        )
    return user
