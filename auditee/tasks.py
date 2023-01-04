import datetime
import logging

from django.db.models import Q

from audit.models import Audit, DraftReportComment
from auditee.utils import get_draft_report_alert_and_email_receivers
from comment.constants import UNRESOLVED
from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL

logger = logging.getLogger('auditee_tasks')


@celery_app.task(name='digest_draft_report_new_suggestions')
def digest_draft_report_new_suggestions() -> dict[str, object]:
    audit_draft_report_query = (
        Q(status__requested=True)
        and Q(status__initiated=True)
        and Q(status__fieldwork=True)
        and Q(status__in_draft_report=True)
        and Q(status__completed=False)
    )

    audits = Audit.objects.filter(audit_draft_report_query)
    date_from = datetime.datetime.now() - datetime.timedelta(days=1)
    audits_with_suggestions = []
    for audit in audits:
        draft_report_comments = DraftReportComment.objects.filter(
            audit=audit,
            comment__is_deleted=False,
            comment__state=UNRESOLVED,
            comment__created_at__gte=date_from,
        )
        digest_receiver = get_draft_report_alert_and_email_receivers(audit.id)
        comments = [df.comment for df in draft_report_comments]
        if comments:
            audits_with_suggestions.append(audit.id)
            hostname = DJANGO_SETTINGS.get('LAIKA_AUDIT_REDIRECT')
            template_context = {
                'draft_report_title': (
                    f'{audit.organization} {audit.audit_type} Draft Report'
                ),
                'comments': comments,
                'call_to_action_url': (
                    f'{hostname}/audits/{audit.id}?'
                    'activeKey=Report%20Creation_Draft%20'
                    'Report&isSubmenu=true'
                ),
                'status_cta': 'VIEW SUGGESTIONS',
            }
            auditors = []
            for auditor in digest_receiver:
                auditors.append(auditor.user.email)
                send_email(
                    subject=(
                        f'Daily digest: {audit.organization}’s draft report suggestions'
                    ),
                    from_email=NO_REPLY_EMAIL,
                    to=[auditor.user.email],
                    template='alert_draft_report_daily_digest.html',
                    template_context=template_context,
                )
            logger.info(
                f'Email was sent successfully to {auditors} '
                f'auditors of audit {audit.id}'
            )
        else:
            logger.info(f'No email  was sent to auditors of audit {audit.id}')

    return {'audits': audits_with_suggestions, 'success': True}
