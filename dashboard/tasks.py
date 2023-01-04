from celery.utils.log import get_task_logger

from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from laika.utils.exceptions import ServiceException
from organization.models import Organization
from user.constants import EMAIL_PREFERENCES
from user.models import User

logger = get_task_logger(__name__)


EMAIL_SUCCESSFULLY_SENT = 1


def _get_template_context(user, total_items, user_pending_items):
    logger.info(
        f'User: {user.email} have {len(user_pending_items)} pending action items.'
    )
    remaining_items = len(total_items) - len(user_pending_items)
    return {
        'pending_action_items': user_pending_items,
        'remaining_items': remaining_items,
        'web_url': DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT'),
    }


def _send_email_with_pending_action_items(user, context):
    return send_email(
        subject='Your Laika Action Items',
        from_email=NO_REPLY_EMAIL,
        to=[user.email],
        template='pending_action_items.html',
        template_context=context,
    )


def _send_pending_action_items(organizations, email_preference, period):
    emails_sent_by_org = {}
    for organization in organizations:
        logger.info(
            f'Sending action items set as {period} in organization: {organization.name}'
        )
        users_per_org = User.objects.filter(
            organization=organization,
            is_active=True,
            user_preferences__profile__emails=email_preference,
        )
        emails_sent = 0
        for user in users_per_org:
            if len(user.all_pending_action_items) > 0:
                send_pending_action_items_by_user_email.delay(user.email)
                emails_sent += 1

        emails_sent_by_org[organization.name] = emails_sent

    return emails_sent_by_org


@celery_app.task(
    bind=True, name='Send pending action items email weekly by organization'
)
def send_pending_action_items_weekly_by_organization(self, *args):
    organizations = (
        Organization.objects.filter(id__in=args) if args else Organization.objects.all()
    )

    emails_sent = _send_pending_action_items(
        organizations, EMAIL_PREFERENCES['WEEKLY'], 'weekly'
    )

    return emails_sent


@celery_app.task(
    bind=True, name='Send pending action items email daily by organization'
)
def send_pending_action_items_daily_by_organization(self, *args):
    organizations = (
        Organization.objects.filter(id__in=args) if args else Organization.objects.all()
    )
    emails_sent = _send_pending_action_items(
        organizations, EMAIL_PREFERENCES['DAILY'], 'daily'
    )
    return emails_sent


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True,
    name='Send pending action items by user email',
)
def send_pending_action_items_by_user_email(self, user_email):
    email_sent = False
    logger.info(f'Sending email to user: {user_email}')
    user = User.objects.get(email=user_email)
    total_items = user.all_pending_action_items

    if len(total_items) > 0:
        user_pending_items = total_items[:5]

        context = _get_template_context(user, total_items, user_pending_items)
        result = _send_email_with_pending_action_items(user, context)
        if result != EMAIL_SUCCESSFULLY_SENT:
            error_message = f'Error sending action items email to user {user.email}'
            logger.exception(error_message)
            raise ServiceException(error_message)

        email_sent = True
        logger.info(f'Email sent to: {user.email}')

    return email_sent
