from functools import wraps

from django.db import transaction

from laika.auth import (
    auditor_required,
    concierge_required,
    login_required,
    permission_required,
    some_login_required,
)
from laika.utils.exceptions import service_exception
from laika.utils.history import create_revision


def laika_service(permission, atomic=True, revision_name=None, exception_msg=''):
    def external_decorator(func):
        if atomic:
            func = transaction.atomic(func)
        if revision_name:
            func = create_revision(revision_name)(func)

        @login_required
        @service_exception(exception_msg)
        @permission_required(permission)
        @wraps(func)
        def decorator(*args, **kwargs):
            return func(*args, **kwargs)

        return decorator

    return external_decorator


def audit_service(permission, atomic=True, revision_name=None, exception_msg=''):
    def external_decorator(func):
        if atomic:
            func = transaction.atomic(func)
        if revision_name:
            func = create_revision(revision_name)(func)

        @auditor_required
        @service_exception(exception_msg)
        @permission_required(permission)
        @wraps(func)
        def decorator(*args, **kwargs):
            return func(*args, **kwargs)

        return decorator

    return external_decorator


def concierge_service(permission, atomic=True, revision_name=None, exception_msg=''):
    def external_decorator(func):
        if atomic:
            func = transaction.atomic(func)
        if revision_name:
            func = create_revision(revision_name)(func)

        @concierge_required
        @service_exception(exception_msg)
        @permission_required(permission)
        @wraps(func)
        def decorator(*args, **kwargs):
            return func(*args, **kwargs)

        return decorator

    return external_decorator


def service(
    allowed_backends,
    atomic=True,
    revision_name=None,
    exception_msg='',
):
    def external_decorator(func):
        if atomic:
            func = transaction.atomic(func)
        if revision_name:
            func = create_revision(revision_name)(func)

        @some_login_required(allowed_backends=allowed_backends)
        @service_exception(exception_msg)
        @wraps(func)
        def decorator(*args, **kwargs):
            return func(*args, **kwargs)

        return decorator

    return external_decorator
