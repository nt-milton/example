import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from laika.storage import PrivateMediaStorage
from organization.models import Organization
from user.models import User
from vendor.models import OrganizationVendor, Vendor


def access_review_upload_directory(instance, filename):
    return f'{instance.id}/{filename}'


def access_review_object_upload_directory(instance, filename):
    access_review = instance.access_review_vendor.access_review
    return f'{access_review.id}/o/{filename}'


def access_review_object_note_attachment_upload_directory(instance, filename):
    access_review = instance.access_review_vendor.access_review
    return f'{access_review.id}/n/{filename}'


class AccessReviewPreference(models.Model):
    class Frequency(models.TextChoices):
        QUARTERLY = 'quarterly', _('Quarterly')
        MONTHLY = 'monthly', _('Monthly')

    class Criticality(models.TextChoices):
        HIGH = 'high', _('High')
        MEDIUM = 'medium', _('Medium')
        LOW = 'low', _('Low')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='access_review_preference',
    )
    frequency = models.CharField(
        max_length=32,
        choices=Frequency.choices,
        default=Frequency.QUARTERLY,
    )
    criticality = models.CharField(
        max_length=32,
        choices=Criticality.choices,
        default=Criticality.LOW,
    )
    due_date = models.DateTimeField(blank=True, null=True)


class AccessReviewVendorPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization_vendor = models.ForeignKey(
        OrganizationVendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_review_vendor_preference',
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='access_review_vendor_preferences',
        null=True,
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='access_review_vendor_preferences',
        null=True,
    )
    in_scope = models.BooleanField(default=False)
    reviewers = models.ManyToManyField(User, blank=True)


class ExternalAccessOwner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='external_access_owners'
    )
    first_name = models.CharField(max_length=64, default='')
    last_name = models.CharField(max_length=64, default='')
    email = models.EmailField(max_length=254)


class AccessReview(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', _('In progress')
        DONE = 'done', _('Done')
        CANCELED = 'canceled', _('Canceled')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='access_reviews'
    )
    name = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        related_name='access_reviews_created',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    due_date = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    notes = models.TextField(blank=True, default='')
    final_report = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=access_review_upload_directory,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f'{self.name}'


class AccessReviewVendor(models.Model):
    class Source(models.TextChoices):
        INTEGRATION = 'integration', _('Integration')
        SSO = 'sso', _('Single Sign-On')
        MANUAL = 'manual', _('Manual')

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', _('Not started')
        IN_PROGRESS = 'in_progress', _('In progress')
        COMPLETED = 'completed', _('Completed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    access_review = models.ForeignKey(AccessReview, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    synced_at = models.DateTimeField(blank=True, null=True)
    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.INTEGRATION,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )


class AccessReviewObject(models.Model):
    class ReviewStatus(models.TextChoices):
        MODIFIED = 'modified', _('Modified')
        REVOKED = 'revoked', _('Revoked')
        UNCHANGED = 'unchanged', _('Unchanged')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    access_review_vendor = models.ForeignKey(
        AccessReviewVendor, on_delete=models.CASCADE
    )
    laika_object = models.ForeignKey(
        'objects.LaikaObject',
        on_delete=models.CASCADE,
        related_name='access_review_objects',
    )
    evidence = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=access_review_object_upload_directory,
        null=True,
        blank=True,
    )
    review_status = models.CharField(
        max_length=32,
        choices=ReviewStatus.choices,
        default=ReviewStatus.UNCHANGED,
    )
    notes = models.TextField(blank=True, default='')
    original_access = models.JSONField(blank=True, null=True)
    latest_access = models.JSONField(blank=True, null=True)
    final_snapshot = models.JSONField(blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    note_attachment = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=access_review_object_note_attachment_upload_directory,
        null=True,
        blank=True,
    )


class AccessReviewUserEvent(models.Model):
    class EventType(models.TextChoices):
        HELP_MODAL_OPENED = 'help_modal_opened'
        CANCEL_ACCESS_REVIEW = 'cancel_access_review'
        CREATE_ACCESS_REVIEW = 'create_access_review'
        COMPLETE_ACCESS_REVIEW = 'complete_access_review'
        COMPLETE_ACCESS_REVIEW_VENDOR = 'complete_access_review_vendor'
        REVIEWED_ACCOUNTS = 'reviewed_accounts'
        UNREVIEWED_ACCOUNTS = 'unreviewed_accounts'
        CREATE_OR_UPDATE_ACCOUNTS_NOTES = 'create_or_update_accounts'
        ADD_ACCOUNT_ATTACHMENT = 'add_accounts_attachment'
        CLEAR_ACCOUNT_ATTACHMENT = 'clear_accounts_attachment'

    access_review_objects = models.ManyToManyField(
        AccessReviewObject, related_name="access_review_user_events"
    )
    access_review_vendor = models.ForeignKey(
        AccessReviewVendor, on_delete=models.CASCADE, null=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    access_review = models.ForeignKey(AccessReview, on_delete=models.CASCADE)
    event = models.TextField(choices=EventType.choices)
    event_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)


class AccessReviewAlert(models.Model):
    alert = models.ForeignKey(
        'alert.Alert',
        related_name='access_review_alert',
        on_delete=models.CASCADE,
    )
    access_review = models.ForeignKey(
        AccessReview, related_name='access_review_alert', on_delete=models.CASCADE
    )
