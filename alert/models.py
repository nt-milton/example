import logging

from django.db import models

from alert.constants import ALERT_ACTIONS, ALERT_TYPES
from alert.utils import (
    send_audit_alert_email,
    send_auditor_alert_email,
    send_comment_control_alert_email,
    send_comment_policy_alert_email,
    send_comment_task_alert_email,
    send_evidence_comment_alert_email,
    should_send_alert_email,
)
from laika.constants import WS_AUDITOR_GROUP_NAME
from laika.settings import DJANGO_SETTINGS
from laika.utils.websocket import send_ws_message_to_group
from user.constants import AUDITOR_ROLES
from user.models import User

logger = logging.getLogger(__name__)

ALERT_TYPE = [
    ('MENTION', 'MENTION'),
    ('REPLY', 'REPLY'),
    ('RESOLVE', 'RESOLVE'),
    ('NEW_ASSIGNMENT', 'NEW_ASSIGNMENT'),
    ('ASSIGNMENT_COMPLETED', 'ASSIGNMENT_COMPLETED'),
    ('AUDIT_REQUESTED', 'AUDIT_REQUESTED'),
    ('AUDIT_INITIATED', 'AUDIT_INITIATED'),
    ('DRAFT_REPORT_AVAILABLE', 'DRAFT_REPORT_AVAILABLE'),
    ('AUDIT_COMPLETE', 'AUDIT_COMPLETE'),
    ('ORG_REQUESTED_AUDIT', 'ORG_REQUESTED_AUDIT'),
    ('ORG_COMPLETED_DRAFT_REPORT', 'ORG_COMPLETED_DRAFT_REPORT'),
    ('ORG_COMPLETED_INITIATION', 'ORG_COMPLETED_INITIATION'),
    ('VENDOR_DISCOVERY', 'VENDOR_DISCOVERY'),
    ('PEOPLE_DISCOVERY', 'PEOPLE_DISCOVERY'),
    ('TRAINING_REMINDER', 'TRAINING_REMINDER'),
    ('SEEDING_FINISH_REMINDER', 'SEEDING_FINISH_REMINDER'),
    ('EVIDENCE_MENTION', 'EVIDENCE_MENTION'),
    ('EVIDENCE_REPLY', 'EVIDENCE_REPLY'),
    ('REQUIREMENT_REPLY', 'REQUIREMENT_REPLY'),
    ('REQUIREMENT_MENTION', 'REQUIREMENT_MENTION'),
    ('ORG_APPROVED_DRAFT_REPORT', 'ORG_APPROVED_DRAFT_REPORT'),
    ('ORG_SUGGESTED_DRAFT_EDITS', 'ORG_SUGGESTED_DRAFT_EDITS'),
    ('AUDITOR_PUBLISHED_DRAFT_REPORT', 'AUDITOR_PUBLISHED_DRAFT_REPORT'),
    ('AUDITEE_DRAFT_REPORT_MENTION', 'AUDITEE_DRAFT_REPORT_MENTION'),
    ('LO_BACKGROUND_CHECK_CHANGED_STATUS', 'LO_BACKGROUND_CHECK_CHANGED_STATUS'),
    (
        'LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER',
        'LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER',
    ),
    (
        'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER',
        'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER',
    ),
    (
        'LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO',
        'LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO',
    ),
    (
        'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_USER_TO_LO',
        'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_USER_TO_LO',
    ),
    (
        'LO_BACKGROUND_CHECK_ACCOUNT_CREDENTIALED',
        'LO_BACKGROUND_CHECK_ACCOUNT_CREDENTIALED',
    ),
    (
        'LO_BACKGROUND_CHECK_TOKEN_DEAUTHORIZED',
        'LO_BACKGROUND_CHECK_TOKEN_DEAUTHORIZED',
    ),
    ('ACCESS_REVIEW_START', 'ACCESS_REVIEW_START'),
    ('ACCESS_REVIEW_COMPLETE', 'ACCESS_REVIEW_COMPLETE'),
]


class AlertManager(models.Manager):
    def custom_create(self, sender, receiver, alert_type):
        is_auditor = AUDITOR_ROLES['AUDITOR'] in receiver.role
        room_id = WS_AUDITOR_GROUP_NAME if is_auditor else receiver.organization.id
        send_ws_message_to_group(
            room_id=room_id, sender=sender, receiver=receiver.email, logger=logger
        )
        alert = super().create(sender=sender, receiver=receiver, type=alert_type)
        return alert


class Alert(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sender = models.ForeignKey(
        User,
        related_name='alert_sender',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # This is in case the user is deleted we still need to display
    # the name in the alerts panel
    sender_name = models.CharField(max_length=100, blank=True)
    receiver = models.ForeignKey(
        User,
        related_name='alerts',
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=50, choices=ALERT_TYPE, blank=True)
    viewed = models.BooleanField(default=False)

    objects = AlertManager()

    @property
    def comment_pool(self):
        if self.type == ALERT_TYPES['EVIDENCE_MENTION']:
            comment_alert = self.comment_alert.first()
            if comment_alert:
                comment = comment_alert.comment
                return comment.evidence_comments.first().pool if comment else None
            else:
                reply = self.reply_alert.first().reply
                return reply.parent.evidence_comments.first().pool if reply else None

        elif self.type == ALERT_TYPES['EVIDENCE_REPLY']:
            reply = self.reply_alert.first().reply
            return reply.parent.evidence_comments.first().pool if reply else None

    def save(self, task_related=None, audit_status=None, *args, **kwargs):
        if self.sender:
            self.sender_name = self.sender.get_full_name().title()
        super(Alert, self).save(*args, **kwargs)

    def send_comment_task_alert_email(self, task_related, hostname=None):
        if not hostname:
            hostname = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
        alert_preference = self.receiver.user_preferences['profile']['alerts']
        if should_send_alert_email(alert_preference):
            send_comment_task_alert_email(
                alert=self, task_related=task_related, hostname=hostname
            )

    def send_comment_control_alert_email(
        self, control_related, hostname=DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
    ):
        alert_preference = self.receiver.user_preferences['profile']['alerts']
        if should_send_alert_email(alert_preference):
            send_comment_control_alert_email(
                alert=self, control_related=control_related, hostname=hostname
            )

    def send_comment_policy_alert_email(
        self, policy_message_data, hostname=DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
    ):
        alert_preference = self.receiver.user_preferences['profile']['alerts']
        if should_send_alert_email(alert_preference):
            send_comment_policy_alert_email(
                alert=self, policy_message_data=policy_message_data, hostname=hostname
            )

    def send_audit_alert_email(self, audit_status):
        send_audit_alert_email(
            alert=self,
            audit_status=audit_status,
            hostname=DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT'),
        )

    def send_auditor_alert_email(self, audit_status):
        send_auditor_alert_email(
            alert=self,
            audit_status=audit_status,
            hostname=DJANGO_SETTINGS.get('LAIKA_AUDIT_REDIRECT'),
        )

    def send_evidence_comment_alert_email(
        self,
        evidence,
        content,
    ):
        is_auditor = AUDITOR_ROLES['AUDITOR'] in self.receiver.role
        hostname = (
            DJANGO_SETTINGS.get('LAIKA_AUDIT_REDIRECT')
            if is_auditor
            else DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
        )

        return send_evidence_comment_alert_email(
            alert=self,
            evidence=evidence,
            content=content,
            hostname=hostname,
            action=ALERT_ACTIONS[self.type],
        )


class PeopleDiscoveryAlert(models.Model):
    quantity = models.IntegerField()
    alert = models.ForeignKey(
        Alert, related_name='people_alert', on_delete=models.CASCADE
    )
