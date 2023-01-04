import json
import logging
from functools import WRAPPER_ASSIGNMENTS, wraps

from django.http.response import HttpResponse

from laika.utils.exceptions import ServiceException
from organization.salesforce.constants import SALESFORCE_API_KEY

logger_name = __name__
logger = logging.getLogger(logger_name)


def require_salesforce_fields(params):
    def decorator(func):
        @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
        def inner(request, *args, **kwargs):
            logger.info(f'Salesforce Webhook Request Params: {params}.')
            try:
                res_body = json.loads(request.body)
                if not all(param in res_body for param in params):
                    logger.warning(
                        'Missing parameters in the body request from Salesforcr.'
                    )
                    return HttpResponse('Params missing', status=400)
                if not res_body.get('Account_ID_18_char__c'):
                    return HttpResponse('SF Id Account missing', status=400)
            except Exception as e:
                logger.exception(
                    'An error happened trying to parse request body from'
                    f' Salesforce: {e}'
                )
                raise e
            return func(request, *args, **kwargs)

        return inner

    return decorator


def check_salesforce_access(request_resolver):
    @wraps(request_resolver)
    def decorator(*args, **kwargs):
        context = args[0] if len(args) == 1 else args[1].context

        logger.info(
            f'Salesforce Webhook Request Context: {context}. Headers: {context.headers}'
        )

        if context.headers.get('Authorization') != SALESFORCE_API_KEY:
            logger.warning('Invalid Salesforce API Key')
            raise ServiceException('Invalid Salesforce API Key')

        operation = f'operation: {request_resolver.__qualname__}'

        try:
            logger.info(f'START Auth Decorator on Salesforce Api Key for {operation}')
            response = request_resolver(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            raise ServiceException(f'Error happened: {e}')

        return response

    return decorator
