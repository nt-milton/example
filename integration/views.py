import json
import logging
from typing import Dict
from urllib.parse import urlparse

import reversion
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from alert.constants import ALERT_TYPES
from feature.constants import onboarding_v2_flag
from integration.checkr.constants import (
    ACCOUNT_CREDENTIALED_TYPE,
    INVITATION_TYPE,
    REPORT_TYPE,
    TOKEN_DEAUTHORIZED,
)
from integration.checkr.mapper import map_background_checks
from integration.checkr.utils import (
    get_connection_by_authentication_field,
    get_user_linked_in_laika_object,
    handle_checkr_events,
)
from integration.models import ConnectionAccount
from integration.store import Mapper
from laika.settings import DJANGO_SETTINGS
from laika.utils.exceptions import format_stack_in_one_line
from objects.models import LaikaObject
from objects.system_types import BACKGROUND_CHECK
from objects.utils import create_background_check_alerts
from user.constants import ONBOARDING
from vendor.models import Vendor

from .alerts import send_integration_failed_email
from .error_codes import NONE, OTHER
from .exceptions import ConfigurationError
from .factory import get_integration
from .log_utils import connection_data, logger_extra
from .models import ERROR, PENDING
from .utils import normalize_integration_name

URL = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')

logger_name = __name__
logger = logging.getLogger(logger_name)


def oauth_callback(request, vendor_name):
    state = request.GET.get('state')
    code = request.GET.get('code', '')
    if not state and code:
        return redirect(return_callback(code, vendor_name))
    oauth_info = oauth_parser(request, vendor_name)
    connection_account = oauth_info['connection_account']
    connection_account.error_code = NONE
    connection_account.status = PENDING
    connection_account.integration_version = (
        connection_account.integration.get_latest_version()
    )
    try:
        integration = get_integration(connection_account)
        integration.callback(**oauth_info)
    except ConfigurationError as e:
        connection_account.status = PENDING
        connection_account.error_code = e.error_code
        connection_account.log_connection_error(e)
        connection_account.save()
    except Exception as exc:
        logger.exception(f'OAuth callback error: {format_stack_in_one_line(exc)}')
        connection_account.error_code = OTHER
        connection_account.status = ERROR
        connection_account.log_error_exception(exc)
        connection_account.save()
    if connection_account.status == ERROR:
        send_integration_failed_email(
            connection_account, connection_account.error_email_already_sent()
        )
    with reversion.create_revision():
        connection_account.save()
        reversion.set_comment(
            f'OAuth callback executed and ended on {connection_account.status} status.'
        )
    return redirect(laika_web_redirect(connection_account))


def laika_web_redirect(connection_account):
    control = connection_account.control
    vendor = connection_account.integration.vendor.name
    if (
        connection_account.organization.state == ONBOARDING
        and not connection_account.organization.is_flag_active(onboarding_v2_flag)
    ):
        # TODO: Change onboarding URL
        return f'{URL}/onboarding/?control={control}'
    return f'{URL}/integrations/{vendor}/{control}'


def get_connection_from_state(request):
    return ConnectionAccount.objects.get(control=request.GET.get('state'))


def _log_callback_error(
    connection_account: ConnectionAccount, callback_request: HttpRequest
) -> None:
    organization_name = connection_account.organization.name
    data = connection_data(connection_account)
    message = (
        'Error processing callback for customer '
        f'{organization_name}, request GET {callback_request.GET}'
    )
    logger.warning(logger_extra(message, **data))
    connection_account.result = callback_request.GET


def oauth_parser(request: HttpRequest, vendor_name: str) -> Dict:
    connection_account: ConnectionAccount = get_connection_from_state(request)
    expected_vendor: str = normalize_integration_name(
        connection_account.integration.vendor.name
    )
    if normalize_integration_name(vendor_name) != expected_vendor:
        raise ValueError(
            f'Vendor {vendor_name} not expected for {expected_vendor} integration'
        )
    backend_url = DJANGO_SETTINGS.get('LAIKA_APP_URL')
    callback_path = reverse(
        'integration:oauth-callback', kwargs={'vendor_name': vendor_name}
    )
    redirect_uri = f'{backend_url}{callback_path}'
    request_code = request.GET.get('code')
    if not request_code:
        _log_callback_error(
            connection_account=connection_account, callback_request=request
        )

    return {
        'code': request_code,
        'redirect_uri': redirect_uri,
        'connection_account': connection_account,
    }


def return_callback(code, vendor_name):
    params = f'code={code}'
    vendor = Vendor.objects.get(name__iexact=vendor_name)
    url = f'{URL}/integrations/{vendor.name}?{params}'
    parsed_uri = urlparse(url)
    return parsed_uri.geturl()


@csrf_exempt
def webhook_checkr(request):
    if request.method != 'POST':
        logger.warning('Webhook only accepts POST requests')
        return HttpResponse('Incorrect incoming method', status=200)

    logger.info(f'Checkr Webhook body - {request.body}')
    payload = json.loads(request.body)
    account_id = payload.get('account_id')
    event_type = payload.get('type')
    payload_object = payload['data']['object']
    object_type = payload_object.get('object')
    is_report_type = object_type == REPORT_TYPE or object_type == INVITATION_TYPE

    candidate_id = (
        payload_object.get('candidate_id')
        if is_report_type
        else payload_object.get('id')
    )

    if event_type == TOKEN_DEAUTHORIZED:
        connection_filter = {
            'key': 'access_token',
            'value': payload_object.get('access_code'),
        }
    else:
        connection_filter = {'key': 'checkr_account_id', 'value': account_id}
    connection_account = get_connection_by_authentication_field(**connection_filter)
    if connection_account is None:
        message = f'Connection account doest not exist for this account_id {account_id}'
        logger.error(message)
        return HttpResponse(message, status=200)
    check_mapper = Mapper(
        map_function=map_background_checks,
        keys=['Id'],
        laika_object_spec=BACKGROUND_CHECK,
    )

    if event_type in [ACCOUNT_CREDENTIALED_TYPE, TOKEN_DEAUTHORIZED]:
        alert_type = ''
        authorized = False
        if event_type == ACCOUNT_CREDENTIALED_TYPE:
            authorized = payload_object.get('authorized')
            alert_type = 'LO_BACKGROUND_CHECK_ACCOUNT_CREDENTIALED'
        elif event_type == TOKEN_DEAUTHORIZED:
            authorized = False
            alert_type = 'LO_BACKGROUND_CHECK_TOKEN_DEAUTHORIZED'
        connection_account.authentication['authorized'] = authorized
        connection_account.save()
        alert_type = ALERT_TYPES.get(alert_type)
        create_background_check_alerts(
            alert_type=alert_type, organization_id=connection_account.organization.id
        )
        return HttpResponse(
            f'Connection Account updated {connection_account.id} with the '
            f'event {event_type}',
            status=200,
        )

    try:
        laika_object = LaikaObject.objects.get(
            data__Id=candidate_id, connection_account__id=connection_account.id
        )
    except LaikaObject.DoesNotExist:
        error_message = (
            f'Laika Object Candidate with ID: {candidate_id} - '
            f'connection account {connection_account.id} '
            'does not exists'
        )
        logger.exception(error_message)
        return HttpResponse(error_message, status=200)

    user_linked = get_user_linked_in_laika_object(laika_object.data)

    try:
        handle_checkr_events(
            event_type,
            object_type,
            payload_object,
            laika_object,
            connection_account,
            check_mapper,
            user_linked,
        )
        return HttpResponse(
            f'Candidate data successfully updated for ID {candidate_id}', status=200
        )
    except Exception as e:
        logger.exception(
            f'Connection account {connection_account.id} '
            f'Error trying to update candidate: {e}'
        )
        return HttpResponse(
            f'Candidate data unsuccessfully updated for ID {candidate_id}', status=200
        )
