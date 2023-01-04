from datetime import datetime

from django.core.files import File

from alert.constants import ALERT_TYPES
from audit.constants import IN_APP_DRAFT_REPORTING_FEATURE_FLAG
from audit.models import Audit, AuditAlert, AuditStatus
from auditor.report.constants import DRAFT_REPORT_VERSION, FINAL_REPORT_VERSION
from auditor.report.report_generator.report_director import ReportDirector
from feature.models import Flag
from laika.aws.ses import send_email
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from user.constants import ROLE_ADMIN
from user.models import User


def alert_users_draft_report_published(audit: Audit, auditor_user: User):
    users = User.objects.filter(organization=audit.organization, role=ROLE_ADMIN)

    hostname = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
    template_context = {
        'status_title': 'Your Draft Report is ready to review.',
        'status_description': f'''A draft {audit.audit_type}
        report for {audit.organization.name} has been
        delivered. Log in to review and approve your report''',
        'call_to_action_url': f'{hostname}/audits/{audit.id}?activeKey=Draft%20Report',
        'status_cta': 'VIEW DRAFT REPORT',
        'audit_type': f'{audit.audit_type}',
    }

    is_in_app_draft_reporting_flag_enabled = Flag.is_flag_enabled_for_organization(
        flag_name=IN_APP_DRAFT_REPORTING_FEATURE_FLAG,
        organization=audit.organization,
    )

    if is_in_app_draft_reporting_flag_enabled:
        for user in users:
            send_email(
                subject='[ACTION REQUIRED] Review your draft audit report',
                from_email=NO_REPLY_EMAIL,
                to=[user.email],
                template='alert_customer_review_draft_report.html',
                template_context=template_context,
            )
            AuditAlert.objects.custom_create(
                audit=audit,
                sender=auditor_user,
                receiver=user,
                alert_type=ALERT_TYPES['AUDITOR_PUBLISHED_DRAFT_REPORT'],
            )


def alert_users_audit_completed(audit_status: AuditStatus):
    alerts = audit_status.create_audit_stage_alerts()
    for alert in alerts:
        alert.send_audit_alert_email(audit_status)


def publish_report(
    audit: Audit, version: str, auditor_user: User, report_publish_date: str = None
):
    report_director = ReportDirector(audit=audit)

    audit_status = audit.status.first()
    organization_name = audit.organization.name
    audit_type = audit.audit_type
    report_name = f'{version.capitalize()} - {organization_name} - {audit_type}.pdf'
    if version == FINAL_REPORT_VERSION:
        pdf = report_director.create_soc_2_final_report_pdf(report_publish_date)
        now = datetime.now()
        audit_status.final_report = File(name=report_name, file=pdf)
        audit_status.final_report_updated_at = report_publish_date
        audit_status.completed = True
        audit.completed_at = now
        audit.save()
        audit_status.save()
        alert_users_audit_completed(audit_status)

    elif version == DRAFT_REPORT_VERSION:
        pdf = report_director.create_soc_2_draft_report_pdf()
        audit_status.draft_report = File(name=report_name, file=pdf)
        audit_status.draft_report_updated_at = datetime.now()
        audit_status.draft_report_name = report_name
        audit_status.save()
        alert_users_draft_report_published(audit, auditor_user)
