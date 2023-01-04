import logging

from laika.aws.ses import send_email
from laika.settings import LAIKA_ADMIN_EMAIL, LAIKA_WEB_REDIRECT, NO_REPLY_EMAIL
from seeder.constants import SEED_EMAIL_TEMPLATE

logger = logging.getLogger(__name__)
LOCALHOST = 'localhost'


def send_email_to_created_by(subject, instance, template_context):
    send_email(
        subject=subject,
        from_email=NO_REPLY_EMAIL,
        to=[instance.created_by.email],
        template=SEED_EMAIL_TEMPLATE,
        template_context=template_context,
    )


def send_email_for_to_admin(subject, template_context):
    send_email(
        subject=subject,
        from_email=NO_REPLY_EMAIL,
        to=[LAIKA_ADMIN_EMAIL],
        template=SEED_EMAIL_TEMPLATE,
        template_context=template_context,
    )


def send_seed_email(instance):
    hostname = LAIKA_WEB_REDIRECT
    subject = 'Organization Seed Complete'

    template_context = {
        'organization_name': instance.organization.name,
        'call_to_action_url_success': f'{hostname}/dashboard',
        'title': subject,
        'subtitle': 'Your seed is ready!',
    }

    if instance.created_by is not None:
        logger.info('Sending email for seeding complete')
        send_email_to_created_by(subject, instance, template_context)
    elif LOCALHOST not in hostname:
        logger.info('Sending email for seeding complete to admin')
        send_email_for_to_admin(subject, template_context)


def send_seed_error_email(instance):
    hostname = LAIKA_WEB_REDIRECT
    subject = 'Organization Seed Failed'

    template_context = {
        'title': subject,
        'subtitle': 'Your seed failed',
        'message_error': 'Something went wrong with the seeding process for "'
        + instance.organization.name
        + '", please contact product.',
    }

    if instance.created_by is not None:
        logger.info('Sending email for seeding error')
        send_email_to_created_by(subject, instance, template_context)
    elif LOCALHOST not in hostname:
        logger.info('Sending email for seeding error to admin')
        send_email_for_to_admin(subject, template_context)
