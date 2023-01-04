import logging

from alert.constants import ALERT_TYPES
from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import DJANGO_SETTINGS, INVITE_NO_REPLY_EMAIL
from program.utils.alerts import create_alert
from training.models import Alumni, TrainingAlert, TrainingAssignee

logger = logging.getLogger('uncompleted_training_email_task')


def get_users_with_uncompleted_trainings():
    assignees = TrainingAssignee.objects.filter(user__organization__isnull=False)

    for training_assignee in assignees:
        has_completed_training = Alumni.objects.filter(
            user=training_assignee.user, training=training_assignee.training
        ).exists()

        if has_completed_training is False:
            yield training_assignee


@celery_app.task(name='Send Training Reminder Email')
def send_training_reminder_email():
    try:
        template_context = {
            'call_to_action_url': (
                f'{DJANGO_SETTINGS.get("LAIKA_WEB_REDIRECT")}/training'
            )
        }

        for training_assignee in get_users_with_uncompleted_trainings():
            logger.info(
                'Sending Training Reminder Email to username: '
                f'{training_assignee.user.username}'
            )

            create_alert(
                room_id=training_assignee.user.organization.id,
                receiver=training_assignee.user,
                alert_type=ALERT_TYPES['TRAINING_REMINDER'],
                alert_related_model=TrainingAlert,
                alert_related_object={'training': training_assignee.training},
            )

            send_email(
                subject='Reminder to complete training',
                from_email=INVITE_NO_REPLY_EMAIL,
                to=[training_assignee.user.email],
                template='uncomplete_trainings_email.html',
                template_context=template_context,
            )

        return {'success': True}
    except Exception as e:
        logger.error(f'Unable to send email {e}')
