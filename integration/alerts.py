import logging
import os
import re
from datetime import date
from typing import Union
from urllib.parse import quote

from integration.error_codes import BAD_CLIENT_CREDENTIALS, CONNECTION_TIMEOUT
from laika.aws.ses import send_email_with_cc
from laika.settings import DJANGO_SETTINGS, INVITE_NO_REPLY_EMAIL, MAIN_ARCHIVE_MAIL

ENVIRONMENT = os.getenv('ENVIRONMENT')

logger = logging.getLogger(__name__)

web_url = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')

DEV_ARCHIVE_MAIL = 'integration.errors@heylaika.com'


def _reconfigure_integration_url(connection_account):
    quote_url = quote(connection_account.integration.vendor.name)
    return f'{web_url}/integrations/{quote_url}'


def _reconfigure_profile_url():
    return f'{web_url}/profile'


def _copy_to_cx_team(connection_account):
    cc_emails = []
    organization = connection_account.organization
    if organization.compliance_architect_user:
        cc_emails.append(organization.compliance_architect_user.email)
    if organization.customer_success_manager_user:
        cc_emails.append(organization.customer_success_manager_user.email)

    if ENVIRONMENT == 'prod':
        cx_support_email = DJANGO_SETTINGS.get('CX_SUPPORT_EMAIL')
        cc_emails.append(cx_support_email)

    return cc_emails


def _get_bbc_emails():
    return [MAIN_ARCHIVE_MAIL] if ENVIRONMENT == 'prod' else []


def _send_email(connection_account) -> bool:
    if (
        not connection_account.send_mail_error
        or connection_account.error_code == CONNECTION_TIMEOUT
    ):
        return False
    return True


def _get_error_solution_message(connection_account, error) -> str:
    alerts_with_regex = connection_account.integration.get_alerts_with_regex(error)
    custom_message = search_error_message_by_regex_result(
        connection_account, alerts_with_regex
    )
    if custom_message:
        return custom_message

    alert_without_regex = connection_account.integration.get_alert_without_regex(error)
    if alert_without_regex:
        return alert_without_regex.error_message

    return error.default_message if error.default_message else ''


def _add_style_html_message(message) -> str:
    style = (
        'style="margin:0;padding:0;color:#232735;            '
        ' font-family:Roboto,Rubik,Arial,Helvetica,Verdana,sans-serif;            '
        ' font-size:14px;line-height:24px;font-weight:400"'
    )
    return message.replace('<p>', f'<p {style}>')


def _get_extra_params_mail(connection_account) -> Union[dict, None]:
    error = connection_account.get_error_in_catalogue()
    if not error:
        logger.warning(
            'Email not sent because not found the error in the '
            f'catalog error in connection {connection_account}'
        )
        return None

    if not error.send_email:
        logger.info(
            f'Email not sent in connection {connection_account} '
            f'because the {error} does not allow it.'
        )
        return None

    requirements = connection_account.integration.get_requirements()
    is_invalid_credentials = connection_account.error_code == BAD_CLIENT_CREDENTIALS
    error_message = _get_error_solution_message(connection_account, error)
    return dict(
        reason_connection_failure=error.failure_reason_mail,
        requirements=requirements,
        is_invalid_credentials=is_invalid_credentials,
        error_message=_add_style_html_message(error_message),
    )


def send_integration_failed_email(connection_account, email_already_sent: bool = False):
    extra_params = _get_extra_params_mail(connection_account)
    if not extra_params:
        return

    if not _send_email(connection_account):
        return

    if not email_already_sent:
        created_by = connection_account.created_by
        full_name = f'{created_by.first_name} {created_by.last_name}'
        vendor = connection_account.integration.vendor
        email_to = created_by.email
        cc_emails = _copy_to_cx_team(connection_account)
        bbc_emails = _get_bbc_emails()

        email_sent = send_email_with_cc(
            subject=f'Integration with {vendor} failed!',
            from_email=INVITE_NO_REPLY_EMAIL,
            to=[email_to],
            template='integration_failed_alert.html',
            template_context={
                'username': full_name,
                'integration': vendor,
                'logo_url': connection_account.integration.email_logo.url,
                'extra': extra_params,
                'reconfigure_integration_url': _reconfigure_integration_url(
                    connection_account
                ),
                'reconfigure_profile_url': _reconfigure_profile_url(),
            },
            cc=cc_emails,
            bbc=bbc_emails,
        )
        if email_sent:
            logger.info(
                f'Email sent to {email_to} with copy to {cc_emails} '
                f'that integration with vendor {vendor} failed on '
                f'connection account: {connection_account.id}'
            )
            connection_account.result['email_sent'] = str(date.today())


def search_error_message_by_regex_result(
    connection_account, integration_alerts: list, is_wizard: bool = False
) -> Union[str, None]:
    error_response = connection_account.result.get('error_response')
    if not error_response or len(integration_alerts) == 0:
        return None
    for integration_alert in integration_alerts:
        if not integration_alert.error_response_regex:
            continue
        error_searched = re.search(
            integration_alert.error_response_regex, error_response
        )
        if error_searched:
            return (
                integration_alert.wizard_message
                if is_wizard
                else integration_alert.error_message
            )
    return None
