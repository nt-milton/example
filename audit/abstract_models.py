from django.db import models

from laika.storage import PrivateMediaStorage
from user.models import User


def audit_draft_report_directory_path(instance, filename):
    audit = instance.audit
    return f'{audit.organization.id}/audit/{audit.name}/{filename}'


class AuditStages(models.Model):
    requested = models.BooleanField(default=False, verbose_name='Requested Stage')
    initiated = models.BooleanField(default=False, verbose_name='Initiated Stage')
    fieldwork = models.BooleanField(default=False, verbose_name='Fieldwork Stage')
    in_draft_report = models.BooleanField(
        default=False, verbose_name='Draft Report Stage'
    )
    completed = models.BooleanField(default=False, verbose_name='Completed Stage')

    initiated_created_at = models.DateTimeField(null=True, blank=True)
    fieldwork_created_at = models.DateTimeField(null=True, blank=True)
    in_draft_report_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class AuditorRequestSteps(models.Model):
    confirm_audit_details = models.BooleanField(default=False)
    engagement_letter_link = models.TextField(blank=True, null=True)
    control_design_assessment_link = models.TextField(blank=True, null=True)
    kickoff_meeting_link = models.TextField(blank=True, null=True)

    engagement_letter_url = models.TextField(blank=True, null=True)
    control_design_assessment_url = models.TextField(blank=True, null=True)

    confirm_audit_details_updated_at = models.DateTimeField(null=True, blank=True)
    engagement_letter_link_updated_at = models.DateTimeField(null=True, blank=True)
    control_design_assessment_link_updated_at = models.DateTimeField(
        null=True, blank=True
    )
    kickoff_meeting_link_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class AuditorInitiatedSteps(models.Model):
    confirm_engagement_letter_signed = models.BooleanField(default=False)
    confirm_control_design_assessment = models.BooleanField(default=False)
    confirm_kickoff_meeting = models.BooleanField(default=False)
    kickoff_call_date = models.DateTimeField(blank=True, null=True)

    confirm_engagement_letter_signed_updated_at = models.DateTimeField(
        null=True, blank=True
    )
    confirm_control_design_assessment_updated_at = models.DateTimeField(
        null=True, blank=True
    )
    confirm_kickoff_meeting_updated_at = models.DateTimeField(null=True, blank=True)
    kickoff_call_date_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class AuditorFieldworkSteps(models.Model):
    complete_fieldwork = models.BooleanField(default=False)
    draft_report_generated = models.BooleanField(default=False)
    representation_letter_link = models.TextField(blank=True, null=True)
    management_assertion_link = models.TextField(blank=True, null=True)
    subsequent_events_questionnaire_link = models.TextField(blank=True, null=True)
    draft_report = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=audit_draft_report_directory_path,
        blank=True,
        null=True,
        max_length=1024,
    )
    draft_report_name = models.CharField(max_length=255, blank=True)
    draft_report_file_generated = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=audit_draft_report_directory_path,
        blank=True,
        null=True,
        max_length=1024,
    )

    representation_letter_url = models.TextField(blank=True, null=True)
    management_assertion_url = models.TextField(blank=True, null=True)
    subsequent_events_url = models.TextField(blank=True, null=True)

    complete_fieldwork_updated_at = models.DateTimeField(null=True, blank=True)
    first_draft_report_generated_timestamp = models.DateTimeField(null=True, blank=True)
    draft_report_generated_updated_at = models.DateTimeField(null=True, blank=True)
    draft_report_checked_timestamp = models.DateTimeField(null=True, blank=True)
    representation_letter_link_updated_at = models.DateTimeField(null=True, blank=True)
    management_assertion_link_updated_at = models.DateTimeField(null=True, blank=True)
    subsequent_events_questionnaire_link_updated_at = models.DateTimeField(
        null=True, blank=True
    )
    draft_report_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class AuditorDraftReportSteps(models.Model):
    confirm_completion_of_signed_documents = models.BooleanField(default=False)
    final_report = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=audit_draft_report_directory_path,
        blank=True,
        null=True,
        max_length=1024,
    )

    confirm_completion_of_signed_documents_updated_at = models.DateTimeField(
        null=True, blank=True
    )
    final_report_updated_at = models.DateTimeField(null=True, blank=True)

    draft_report_approved = models.BooleanField(default=False)
    draft_report_approved_timestamp = models.DateTimeField(null=True, blank=True)
    draft_report_approved_by = models.ForeignKey(
        User,
        related_name='draft_report_approved_by',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class AuditorSteps(
    AuditorRequestSteps,
    AuditorInitiatedSteps,
    AuditorFieldworkSteps,
    AuditorDraftReportSteps,
):
    class Meta:
        abstract = True
