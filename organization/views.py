import http
import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from organization.salesforce.constants import sf_params
from organization.salesforce.decorators import (
    check_salesforce_access,
    require_salesforce_fields,
)
from organization.salesforce.implementation import update_or_create_organization
from organization.slack_post_message import post_error_message

logger_name = __name__
logger = logging.getLogger(logger_name)


@check_salesforce_access
@csrf_exempt
@require_salesforce_fields(params=sf_params)
@require_http_methods(["POST"])
def webhook_salesforce(request):
    if request.method != 'POST':
        logger.warning('Salesforce webhook only accepts POST requests')
        return HttpResponse(
            'Incorrect incoming method', status=http.HTTPStatus.METHOD_NOT_ALLOWED
        )
    try:
        logger.info(f'Salesforce Webhook body - {request.body}')
        organization, status_detail = update_or_create_organization(
            salesforce_adapter(request)
        )
        if status_detail:
            post_error_message('\n\n'.join(status_detail))
        if not organization:
            return HttpResponse(
                'Failed to sync the organization.',
                status=http.HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        return HttpResponse(organization.id, status=http.HTTPStatus.OK)
    except Exception as e:
        logger.warning(f'Error trying to sync org: {e}')
        post_error_message(
            f'Error trying to sync organization from salesforce webhook: {e}'
        )
        return HttpResponse(
            'Failing to sync the organization.',
            status=http.HTTPStatus.INTERNAL_SERVER_ERROR,
        )


def salesforce_adapter(request):
    payload = json.loads(request.body)
    return payload
