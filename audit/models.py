import io
from datetime import datetime

from django.core.files import File
from django.db import models

from alert.constants import SLACK_AUDIT_ALERTS
from alert.models import Alert
from audit.constants import (
    AUDIT_FRAMEWORK_TYPES,
    AUDIT_STATUS_ALERTS,
    AUDIT_STATUS_STEPS_FIELDS,
    AUDIT_STATUS_TRACK_UPDATED_FIELDS,
    CURRENT_AUDIT_STATUS,
    DRAFT_REPORT_SECTIONS,
    LEAD_AUDITOR_KEY,
    TITLE_ROLES,
)
from audit.utils.audit import get_current_status
from certification.models import Certification
from comment.models import Comment
from coupon.models import Coupon
from laika.constants import WS_AUDITOR_GROUP_NAME
from laika.storage import PrivateMediaStorage
from laika.utils.exceptions import ServiceException
from organization.models import Organization
from program.utils.alerts import create_alert
from user.models import Auditor, User

from .abstract_models import AuditorSteps, AuditStages


def audit_report_directory_path(instance, filename):
    return f'{instance.organization.id}/audit/{instance.name}/{filename}'


def audit_logos_directory_path(instance, filename):
    return f'{instance.organization.id}/audit/{instance.type}/{filename}'


def audit_exported_directory_path(instance, filename):
    organization_id = instance.organization.id
    audit = instance.name
    return f'{organization_id}/audit/{audit}/exported/{filename}'


def framework_templates_file_directory_path(instance, filename):
    return f'audit/{instance.audit_framework_type.audit_type}/templates/{filename}'


def report_template_file_directory_path(instance, filename):
    return (
        f'{instance.audit.organization.id}/audit/'
        f'{instance.audit.id}/templates/{filename}'
    )


def should_create_audit_alert(new_status):
    return new_status in [
        CURRENT_AUDIT_STATUS['INITIATED'],
        CURRENT_AUDIT_STATUS['FIELDWORK'],
        CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT'],
        CURRENT_AUDIT_STATUS['COMPLETED'],
    ]


class AuditFrameworkType(models.Model):
    certification = models.ForeignKey(
        Certification, related_name='audit_type', on_delete=models.CASCADE
    )

    audit_type = models.CharField(
        max_length=50, choices=AUDIT_FRAMEWORK_TYPES, blank=True
    )

    description = models.TextField(blank=True)

    class Meta:
        unique_together = [['certification', 'audit_type']]

    def __str__(self):
        return self.audit_type


class AuditFeedbackReason(models.Model):
    audit_framework_type = models.ForeignKey(
        AuditFrameworkType,
        related_name='feedback_reason',
        on_delete=models.CASCADE,
    )
    reason = models.CharField(max_length=200, default='')


class UnlockedAuditFrameworkTypeOrganization(models.Model):
    class Meta:
        unique_together = (('organization', 'audit_framework_type'),)

    organization = models.ForeignKey(
        Organization,
        related_name='unlocked_audit_frameworks',
        on_delete=models.CASCADE,
    )

    audit_framework_type = models.ForeignKey(
        AuditFrameworkType,
        related_name='unlocked_organizations',
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return self.audit_framework_type.audit_type


class FrameworkReportTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=512, default='')
    section = models.CharField(max_length=20, choices=DRAFT_REPORT_SECTIONS, blank=True)
    audit_framework_type = models.ForeignKey(
        AuditFrameworkType, on_delete=models.CASCADE, related_name='templates'
    )
    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=framework_templates_file_directory_path,
        blank=True,
        max_length=1024,
    )

    def __str__(self):
        return self.name


class AuditFirm(models.Model):
    name = models.CharField(max_length=200)
    signature_text = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class Audit(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization,
        related_name='audits',
        on_delete=models.CASCADE,
    )
    customer_success_manager = models.ForeignKey(
        User,
        related_name='csm_audits',
        on_delete=models.SET_NULL,
        null=True,
    )
    compliance_architect = models.ForeignKey(
        User, related_name='ca_audits', on_delete=models.SET_NULL, null=True
    )
    name = models.CharField(max_length=200)
    audit_type = models.CharField(max_length=100)
    audit_framework_type = models.ForeignKey(
        AuditFrameworkType,
        related_name='audits',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    audit_configuration = models.JSONField(blank=True, default=dict)
    audit_firm = models.ForeignKey(
        AuditFirm,
        related_name='audit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    report = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=audit_report_directory_path,
        blank=True,
        null=True,
        max_length=1024,
    )
    auto_fetch_executed = models.BooleanField(default=False, blank=True, null=True)
    is_demo = models.BooleanField(default=False)

    exported_audit_file = models.FileField(
        storage=PrivateMediaStorage(file_overwrite=True),
        upload_to=audit_exported_directory_path,
        blank=True,
        null=True,
        max_length=2024,
    )

    # This is for detecting soc 2 type 1's that will use the report v2 vs v1
    use_new_version = models.BooleanField(default=False, blank=True, null=True)

    @property
    def lead_auditor(self):
        auditor_lead = AuditAuditor.objects.filter(
            audit_id=self.id, title_role=LEAD_AUDITOR_KEY
        ).first()

        return auditor_lead.auditor.user if auditor_lead else None

    def save(self, *args, **kwargs):
        if self._state.adding:
            organization = self.organization
            coupon = Coupon.objects.filter(
                organization=organization, type=f'{self.audit_type} {self.audit_firm}'
            ).first()

            if not coupon or not coupon.coupons:
                raise ServiceException('No coupons available')

            coupon.coupons -= 1
            coupon.save()
            self.customer_success_manager = organization.customer_success_manager_user
            self.compliance_architect = organization.compliance_architect_user

        audit_framework_type_keys = dict(AUDIT_FRAMEWORK_TYPES)
        audit_type_value = audit_framework_type_keys[
            self.audit_framework_type.audit_type
        ]
        self.audit_type = audit_type_value

        super(Audit, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        audit_alerts = AuditAlert.objects.filter(audit=self)
        alerts = None
        if audit_alerts:
            alerts = [audit_alert.alert for audit_alert in audit_alerts]

        comments = Comment.objects.filter(draft_report_comments__audit=self)
        Alert.objects.filter(
            comment_alert__comment__draft_report_comments__audit=self
        ).delete()
        Alert.objects.filter(reply_alert__reply__parent__in=comments).delete()

        super(Audit, self).delete(*args, **kwargs)
        if alerts:
            for alert in alerts:
                alert.delete()

    def __str__(self):
        return self.name

    def add_section_files(self, sections: list[dict]):
        AuditReportSection.objects.bulk_create(
            [
                AuditReportSection(
                    name=section['name'],
                    file=section['file'],
                    section=section['section'],
                    audit=self,
                )
                for section in sections
            ]
        )


class AuditStatus(AuditStages, AuditorSteps):  # type: ignore
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    audit = models.ForeignKey(
        Audit,
        related_name='status',
        on_delete=models.CASCADE,
    )
    # Initiated stage client steps
    engagement_letter_checked = models.BooleanField(default=False)
    control_design_assessment_checked = models.BooleanField(default=False)
    kickoff_meeting_checked = models.BooleanField(default=False)
    # Draft report stage client steps
    review_draft_report_checked = models.BooleanField(default=False)
    representation_letter_checked = models.BooleanField(default=False)
    management_assertion_checked = models.BooleanField(default=False)
    subsequent_events_questionnaire_checked = models.BooleanField(default=False)

    def create_audit_stage_alerts(self):
        organization = self.audit.organization
        receivers = User.objects.filter(
            organization=organization,
            role__contains='Admin',
        ).exclude(role='AuditorAdmin')
        current_status = get_current_status(self)
        should_create_alert = should_create_audit_alert(current_status)
        audit_firm_name = (
            self.audit.audit_firm.name if self.audit.audit_firm.name else ''
        )
        alerts = []
        if should_create_alert:
            # importing here because it gives circular
            # dependency error if imported from global
            from integration.slack.implementation import send_alert_to_slack
            from integration.slack.types import SlackAlert

            alert_type = AUDIT_STATUS_ALERTS[current_status]
            if alert_type in SLACK_AUDIT_ALERTS:
                slack_alert = SlackAlert(
                    alert_type=alert_type,
                    audit=self.audit.audit_type,
                    receiver=receivers.first(),
                )
                send_alert_to_slack(slack_alert)
            for receiver in receivers:
                alert = create_alert(
                    room_id=organization.id,
                    receiver=receiver,
                    alert_type=alert_type,
                    alert_related_model=AuditAlert,
                    alert_related_object={'audit': self.audit},
                    audit_status=self,
                    sender_name=audit_firm_name,
                )
                alerts.append(alert)
        return alerts

    def create_auditor_alert(self, sender, receiver, alert_type):
        return create_alert(
            room_id=WS_AUDITOR_GROUP_NAME,
            receiver=receiver,
            alert_type=alert_type,
            alert_related_model=AuditAlert,
            sender=sender,
            alert_related_object={'audit': self.audit},
            audit_status=self,
        )

    def track_steps_metrics(self, field):
        if (
            field == AUDIT_STATUS_STEPS_FIELDS['DRAFT_REPORT_GENERATED']
            and not self.draft_report_generated
        ):
            self.first_draft_report_generated_timestamp = datetime.now()
        self.save()

    def update_check_field(self, field: str, is_document_completed: bool):
        if (is_document_completed and not getattr(self, field)) or (
            not is_document_completed and getattr(self, field)
        ):
            setattr(self, field, is_document_completed)
            self.save()


class AuditFeedback(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    audit = models.OneToOneField(
        Audit, related_name='audit_feedback', on_delete=models.CASCADE, primary_key=True
    )
    rate = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    feedback = models.TextField(null=True, blank=True)
    reason = models.JSONField(null=True, blank=True)
    user = models.ForeignKey(
        User,
        related_name='audit_feedback',
        on_delete=models.SET_NULL,
        null=True,
    )


class AuditAlertManager(models.Manager):
    def custom_create(self, audit, sender, receiver, alert_type):
        alert = Alert.objects.custom_create(
            sender=sender, receiver=receiver, alert_type=alert_type
        )
        audit_alert = super().create(alert=alert, audit=audit)
        return audit_alert


class AuditAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='audit_alert', on_delete=models.CASCADE
    )
    audit = models.ForeignKey(
        Audit,
        related_name='alerts',
        on_delete=models.CASCADE,
    )

    objects = AuditAlertManager()


class AuditAuditor(models.Model):
    audit = models.ForeignKey(
        Audit, related_name='audit_team', on_delete=models.CASCADE
    )

    auditor = models.ForeignKey(
        Auditor, related_name='audit_team', on_delete=models.CASCADE
    )

    title_role = models.CharField(
        max_length=50, choices=TITLE_ROLES, blank=False, default='required'
    )

    def __str__(self):
        return f'{self.auditor.user.first_name} {self.auditor.user.last_name}'


class AuditorAuditFirm(models.Model):
    auditor = models.ForeignKey(Auditor, on_delete=models.CASCADE)
    audit_firm = models.ForeignKey(
        AuditFirm, on_delete=models.CASCADE, related_name='firm_auditors'
    )


class OrganizationAuditFirm(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    audit_firm = models.ForeignKey(
        AuditFirm, on_delete=models.CASCADE, related_name='firm_organizations'
    )


class AuditStepTimestampManager(models.Manager):
    def custom_create(self, updated_step, audit_status, updated_at):
        if updated_step in AUDIT_STATUS_TRACK_UPDATED_FIELDS:
            super().create(
                updated_step=updated_step,
                audit_status=audit_status,
                updated_at=updated_at,
            )


class AuditStepTimestamp(models.Model):
    audit_status = models.ForeignKey(
        AuditStatus,
        on_delete=models.CASCADE,
    )
    updated_step = models.CharField(max_length=100)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AuditStepTimestampManager()


class DraftReportCommentManager(models.Manager):
    def custom_create(
        self,
        owner,
        content,
        audit_id,
        tagged_users,
        page,
    ):
        comment = Comment.objects.create(owner=owner, content=content)

        comment.add_mentions(tagged_users)

        audit = Audit.objects.get(pk=audit_id)

        draft_report_comment = super().create(audit=audit, comment=comment, page=page)

        return draft_report_comment


class DraftReportComment(models.Model):
    audit = models.ForeignKey(
        Audit, on_delete=models.CASCADE, related_name='draft_report_comments'
    )

    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name='draft_report_comments'
    )

    page = models.IntegerField(blank=True, null=True)

    is_latest_version = models.BooleanField(default=True)

    auditor_notified = models.BooleanField(default=False)

    def update(self, user, input):
        self.comment.update(user, input)
        if input.get('page'):
            self.page = input.get('page')
            self.save()
        return self

    objects = DraftReportCommentManager()


class AuditReportSection(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=512, default='')
    section = models.CharField(max_length=20, choices=DRAFT_REPORT_SECTIONS, blank=True)
    audit = models.ForeignKey(
        Audit, on_delete=models.CASCADE, related_name='report_sections'
    )
    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=report_template_file_directory_path,
        blank=True,
        max_length=1024,
    )

    def __str__(self):
        return self.name

    def save_draft_report_content(self, content: str, section: str):
        new_file = File(
            name=f'{section}.html',
            file=io.BytesIO(content.encode()),
        )

        self.file = new_file
        self.save()
