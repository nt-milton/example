from django.db import models

from laika.storage import PrivateMediaStorage
from organization.models import Organization
from user.models import User

DEFAULT_PROGRESS_OPTION = 'REQUESTED'

PROGRESS_OPTIONS = (
    ('REQUESTED', 'Requested'),
    ('IN_PROGRESS', 'In Progress'),
    ('COMPLETED', 'Completed'),
    ('CLOSED', 'Closed'),
)

CONCIERGE_TYPES = (
    ('policy', 'Draft a New Policy Document'),
    ('ddq', 'Help with a Diligence Questionnaire'),
    ('time', 'Schedule Time with a Laika Compliance & Security Expert'),
    ('risk_assesment', 'Schedule a Risk Assessment'),
    ('request_unlock', 'Unlock Certification'),
    ('request_integration', 'Request Integration'),
)


def concierge_request_directory_path(instance, filename):
    return f'concierge/{instance.request_type}/{filename}'


class ConciergeRequest(models.Model):
    class Meta:
        permissions = [
            ('change_conciergerequest_status', 'Can change concierge request status')
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        related_name='concierge_requests',
        null=True,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='concierge_requests',
        blank=True,
        null=True,
    )
    file = models.FileField(
        storage=PrivateMediaStorage(),
        max_length=1024,
        upload_to=concierge_request_directory_path,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=PROGRESS_OPTIONS, default=DEFAULT_PROGRESS_OPTION
    )
    request_type = models.CharField(
        max_length=50, choices=CONCIERGE_TYPES, default='REQUESTED'
    )
    description = models.TextField()
    additional_information = models.TextField(blank=True)

    def __str__(self):
        return self.request_type

    def requested_email(self):
        if self.created_by:
            return self.created_by.email
