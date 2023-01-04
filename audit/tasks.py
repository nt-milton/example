import logging

from audit.models import Audit
from audit.utils.export import export_audit_file
from audit.utils.tags import link_subtasks_evidence_to_tags
from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import DJANGO_SETTINGS, INVITE_NO_REPLY_EMAIL, ORIGIN_LOCALHOST
from user.models import User

logger = logging.getLogger('audit_email_task')


@celery_app.task(name='Send Audit Invite User Email')
def send_audit_invite_user_email(user_email, context):
    log_in_url = DJANGO_SETTINGS.get('LAIKA_AUDIT_REDIRECT') or ORIGIN_LOCALHOST[2]
    template_context = {**context, 'log_in_url': log_in_url}

    logger.info(f'Sending audit invite email to: {user_email}')
    send_email(
        subject='You’ve been invited to Laika!',
        from_email=INVITE_NO_REPLY_EMAIL,
        to=[user_email],
        template='invite_audit_user_email.html',
        template_context=template_context,
    )


@celery_app.task(name='Link evidence to tags')
def link_evidence_to_tags(organization_id: str) -> None:
    logger.info(f'Task for linking org: {organization_id} evidence to tags')
    link_subtasks_evidence_to_tags(organization_id)


@celery_app.task(name='Export audit')
def export_audit(audit_id: str, user: User) -> None:
    audit = Audit.objects.get(id=audit_id)

    organization_id = audit.organization.id
    logger.info(
        f'Task exporting audit: {audit_id} data for organization: {organization_id}'
    )
    export_audit_file(audit, user)
