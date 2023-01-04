import logging
import re
from multiprocessing.pool import ThreadPool

from laika.aws.ses import send_email, send_email_with_cc
from laika.constants import OKTA
from laika.settings import INVITE_NO_REPLY_EMAIL, LAIKA_WEB_REDIRECT, ORIGIN_LOCALHOST
from laika.utils.regex import URL_DOMAIN_NAME
from user.constants import DELEGATION_PATHS, INVITATION_TYPES

logger = logging.getLogger(__name__)
pool = ThreadPool()


def format_super_admin_email(email='', website=''):
    tokens = email.split('@')
    matches = re.search(URL_DOMAIN_NAME, website)
    new_email = f'{tokens[0]}+{matches.group(1)}@{tokens[1]}'
    return new_email


def get_delegation_path(org_state) -> str:
    return DELEGATION_PATHS.get(org_state, DELEGATION_PATHS['ACTIVE'])


def send_invite_email(user_email, context):
    login_link = LAIKA_WEB_REDIRECT or ORIGIN_LOCALHOST[2]

    if context.get('invitation_type') == INVITATION_TYPES['DELEGATION']:
        login_link += get_delegation_path(context.get('organization_state'))

    magic_token = context.get('magic_token')
    params = f"?magic={magic_token}" if magic_token else ''
    template_context = {
        'login_link': f"{login_link}{params}",
        **context,
    }

    logger.info(f'Sending invite email to: {user_email}')
    template = (
        'email/invite_user_okta.html'
        if context.get('idp') == OKTA
        else 'email/invite_user.html'
    )
    if context.get('invitation_type') == INVITATION_TYPES['DELEGATION']:
        pool.apply_async(
            send_email_with_cc,
            kwds=dict(
                subject=context.get('subject'),
                from_email=INVITE_NO_REPLY_EMAIL,
                to=[user_email],
                cc=context.get('cc'),
                bbc=context.get('bbc'),  # bcc
                template='onboarding_delegate_integration.html',
                template_context=template_context,
            ),
        ),
    else:
        pool.apply_async(
            send_email,
            kwds=dict(
                subject='Welcome to Laika!',
                from_email=INVITE_NO_REPLY_EMAIL,
                to=[user_email],
                template=template,
                template_context=template_context,
            ),
        )
