import logging
import traceback
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


def format_stack_in_one_line(ex):
    return ''.join(traceback.format_exception(type(ex), ex, ex.__traceback__))


class HandledException(Exception):
    pass


class ServiceException(Exception):
    pass


def service_exception(message):
    def exception_handler_decorator(function):
        @wraps(function)
        def decorator(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except ObjectDoesNotExist as e:
                context = args[0] if len(args) == 1 else args[1].context
                logger.warning(
                    f'module: {function.__module__} Error: {str(e)} '
                    f'Service message: {message}. '
                    f'Request: {kwargs}, '
                    f'organization {context.user.organization_id}.'
                )
                raise HandledException('Not found')
            except ServiceException as e:
                logger.warning(
                    f'module: {function.__module__} Error calling '
                    f'{function.__qualname__}: {str(e)}, '
                    f'stack: {format_stack_in_one_line(e)}'
                )
                raise HandledException(e)
            except Exception as e:
                logger.exception(
                    f'module: {function.__module__} Error calling '
                    f'{function.__qualname__}: {str(e)}, '
                    f'stack: {format_stack_in_one_line(e)}'
                )
                raise HandledException(message)

        return decorator

    return exception_handler_decorator


GENERIC_FILES_ERROR_MSG = 'Failed to add files. Please try again.'
