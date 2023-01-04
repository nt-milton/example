import logging
import os
from typing import List

import boto3
from django.core.mail import EmailMultiAlternatives

from laika.aws.secrets import REGION_NAME
from laika.settings import DJANGO_SETTINGS
from laika.utils.templates import render_template

LEGACY_AWS_ACCESS_KEY = os.getenv('LEGACY_AWS_ACCESS_KEY')
LEGACY_AWS_SECRET_ACCESS_KEY = os.getenv('LEGACY_AWS_SECRET_ACCESS_KEY')
USER_POOL_ID = DJANGO_SETTINGS.get('LEGACY_POOL_ID')

logger = logging.getLogger('ses_email')

session = boto3.session.Session()
ses = session.client(
    'ses',
    region_name=REGION_NAME,
    aws_access_key_id=LEGACY_AWS_ACCESS_KEY,
    aws_secret_access_key=LEGACY_AWS_SECRET_ACCESS_KEY,
)
MESSAGE_SENT = 1


def send_email(
    subject: str,
    from_email: str,
    to: List[str],
    template: str,
    template_context: dict,
    message: str = '',
):
    html = render_template(template, template_context) if template else ''

    logger.info(f'Trying to send email from ses to: {to}')
    try:
        email_result = send_ses(from_email, to, subject, html, message)
        logger.info(f'Email sent successfully to {to}. Email result {email_result}')
        return MESSAGE_SENT
    except Exception as e:
        logger.warning(f'Error sending email: {e}')
        return None


def send_ses(from_email: str, to: List[str], subject: str, html: str, message: str):
    return ses.send_email(
        Destination={
            'ToAddresses': to,
        },
        Message={
            'Subject': {'Data': subject, 'Charset': 'UTF-8'},
            'Body': {
                'Html': {'Data': html, 'Charset': 'UTF-8'},
                'Text': {'Data': message, 'Charset': 'UTF-8'},
            },
        },
        ReplyToAddresses=[],
        Source=from_email,
    )


def send_email_with_cc(
    subject, from_email, to, template, template_context, message='', cc=None, bbc=None
) -> bool:
    if cc is None:
        cc = []

    bbc = bbc if bbc is not None else []

    html = render_template(template, template_context) if template else ''

    logger.info('Sending email from ses')
    email = EmailMultiAlternatives(
        subject=subject, body=message, from_email=from_email, to=to, bcc=bbc, cc=cc
    )

    email.attach_alternative(html, 'text/html')
    email_result = email.send()
    if email_result == 1:
        logger.info('Email sent successfully!')
        return True
    else:
        logger.warning('Error sending the email!')
        return False
