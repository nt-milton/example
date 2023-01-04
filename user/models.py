import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import django.utils.timezone as timezone
import reversion
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.query_utils import Q
from django.utils.translation import gettext_lazy as _

from feature.constants import mfa_feature_flag
from laika.aws.cognito import delete_cognito_users, get_user
from laika.okta.api import OktaApi
from laika.storage import PrivateMediaStorage
from laika.utils.exceptions import ServiceException
from organization.models import Organization
from search.search import launchpad_model, searchable_model
from user.constants import ALERT_PREFERENCES, EMAIL_PREFERENCES
from user.launchpad import launchpad_mapper

logger = logging.getLogger('user')

OktaApi = OktaApi()

DEFAULT_WATCHER_ROLES = ['OrganizationAdmin']
TWENTY_MINUTES = 20
SEVEN_DAYS = 7

ROLES = [
    ('SuperAdmin', 'SuperAdmin'),
    ('OrganizationAdmin', 'OrganizationAdmin'),
    ('OrganizationMember', 'OrganizationMember'),
    ('OrganizationViewer', 'OrganizationViewer'),
    ('OrganizationSales', 'OrganizationSales'),
    ('AuditorAdmin', 'AuditorAdmin'),
    ('Auditor', 'Auditor'),
    ('Partner', 'Partner'),
    ('Concierge', 'Concierge'),
]

MEMBER_ROLES = [('Chair', 'Chair'), ('Member', 'Member')]

NOT_STARTED = 'not_started'

DISCOVERY_STATE_CONFIRMED = 'Confirmed'
DISCOVERY_STATE_NEW = 'New'
DISCOVERY_STATE_IGNORED = 'Ignored'
DISCOVERY_STATES = [
    (DISCOVERY_STATE_NEW, DISCOVERY_STATE_NEW),
    (DISCOVERY_STATE_IGNORED, DISCOVERY_STATE_IGNORED),
    (DISCOVERY_STATE_CONFIRMED, DISCOVERY_STATE_CONFIRMED),
]

EMPLOYMENT_STATUS_POTENTIAL_HIRE = 'potential_hire'
EMPLOYMENT_STATUS_ACTIVE = 'active'
EMPLOYMENT_STATUS_INACTIVE = 'inactive'

EMPLOYMENT_STATUS = [
    (EMPLOYMENT_STATUS_POTENTIAL_HIRE, 'Potential Hire'),
    (EMPLOYMENT_STATUS_ACTIVE, 'Active'),
    (EMPLOYMENT_STATUS_INACTIVE, 'Inactive'),
]

BACKGROUND_CHECK_STATUS_NA = 'na'
BACKGROUND_CHECK_STATUS_PENDING = 'pending'
BACKGROUND_CHECK_STATUS_PASSED = 'passed'
BACKGROUND_CHECK_STATUS_FLAGGED = 'flagged'
BACKGROUND_CHECK_STATUS_SUSPENDED = 'suspended'
BACKGROUND_CHECK_STATUS_CANCELLED = 'canceled'
BACKGROUND_CHECK_STATUS_EXPIRED = 'expired'

BACKGROUND_CHECK_STATUS = [
    (BACKGROUND_CHECK_STATUS_NA, 'N/A'),
    (BACKGROUND_CHECK_STATUS_PENDING, 'Pending'),
    (BACKGROUND_CHECK_STATUS_PASSED, 'Passed'),
    (BACKGROUND_CHECK_STATUS_FLAGGED, 'Flagged'),
    (BACKGROUND_CHECK_STATUS_SUSPENDED, 'Suspended'),
    (BACKGROUND_CHECK_STATUS_CANCELLED, 'Canceled'),
    (BACKGROUND_CHECK_STATUS_EXPIRED, 'Expired'),
]

concierge_help_text = '''
    first_name, last_name, email, role, password and username (email)
    are required when creating a new concierge user.
    '''


class EmploymentType(models.TextChoices):
    CONTRACTOR = 'contractor', 'Contractor'
    EMPLOYEE = 'employee', 'Employee'


class EmploymentSubtype(models.TextChoices):
    FULL_TIME = 'full_time', 'Full-time'
    PART_TIME = 'part_time', 'Part-time'
    INTERN = 'intern', 'Intern'
    TEMPORARY = 'temp', 'Temporary'
    SEASONAL = 'seasonal', 'Seasonal'
    INDIVIDUAL_CONTRACTOR = 'individual_contractor', 'Individual Contractor'


def default_user_preferences():
    return dict(
        profile=dict(
            alerts=ALERT_PREFERENCES['IMMEDIATELY'], emails=EMAIL_PREFERENCES['DAILY']
        )
    )


def user_picture_directory_path(instance, filename):
    return f'users/{instance.email}/{filename}'


class UserQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs):
        for user in self:
            user.delete()

        super(UserQuerySet, self).delete(*args, **kwargs)

    def hard_delete(self):
        return super(UserQuerySet, self).delete()

    def alive(self):
        return self.filter(deleted_at=None)

    def dead(self):
        return self.exclude(deleted_at=None)


class UserSoftDeleteManager(UserManager):
    def get_queryset(self):
        return UserQuerySet(self.model).filter(deleted_at=None)


class UserCustomManager(UserManager):
    def only_deleted(self):
        return self.get_queryset().exclude(deleted_at__isnull=True)


@launchpad_model(context='user', mapper=launchpad_mapper)
class User(AbstractUser):
    class Meta:
        ordering = ['organization', 'first_name']
        constraints = [
            models.UniqueConstraint(
                fields=['email'], name='unique_email', condition=Q(deleted_at=None)
            )
        ]

    objects = UserSoftDeleteManager()
    # all_objects will return both soft-deleted and alive users
    all_objects = UserCustomManager()

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=100, choices=ROLES, blank=True)
    # Username not unique because we need to create partial users
    username = models.CharField(
        _('username'),
        max_length=150,
        help_text=_(
            'Required. 150 characters or fewer.            Letters, digits and'
            ' @/./+/-/_ only.'
        ),
    )
    user_preferences = models.JSONField(blank=True, default=default_user_preferences)
    profile_picture = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=user_picture_directory_path,
        blank=True,
        null=True,
        max_length=1024,
    )
    title = models.CharField(max_length=100, blank=True, null=True)
    manager = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='manager_user',
        null=True,
        blank=True,
    )
    department = models.CharField(max_length=200, blank=True, null=True)
    employment_type = models.CharField(
        max_length=100, blank=True, null=True, choices=EmploymentType.choices
    )
    employment_subtype = models.CharField(
        max_length=100, blank=True, null=True, choices=EmploymentSubtype.choices
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    background_check_status = models.CharField(
        blank=True, choices=BACKGROUND_CHECK_STATUS, max_length=50, null=True
    )
    background_check_passed_on = models.DateTimeField(null=True, blank=True)
    employment_status = models.CharField(
        null=True, blank=True, max_length=100, choices=EMPLOYMENT_STATUS
    )
    phone_number = models.CharField(max_length=100, blank=True, null=True)
    connection_account = models.ForeignKey(
        'integration.ConnectionAccount',
        on_delete=models.SET_NULL,
        related_name='people',
        blank=True,
        null=True,
    )
    mfa = models.BooleanField(default=False)
    discovery_state = models.CharField(
        max_length=25, choices=DISCOVERY_STATES, default=DISCOVERY_STATE_CONFIRMED
    )
    finch_uuid = models.CharField(max_length=100, blank=True, null=True)
    compliant_completed = models.BooleanField(default=False)
    security_training = models.BooleanField(default=False)
    assigned_trainings_completed = models.BooleanField(default=True)
    policies_reviewed = models.BooleanField(default=True)
    invitation_sent = models.DateTimeField(blank=True, null=True)
    password_expired = models.BooleanField(default=False)

    def delete_from_identity_provider(self):
        if get_user(self.email):
            delete_cognito_users([self.email])
        else:
            logger.warning(f'User {self.email} not found in Cognito.')

        okta_user = OktaApi.get_user_by_email(self.email)
        if okta_user and okta_user.id and okta_user.status == 'ACTIVE':
            OktaApi.delete_user(okta_user.id)
        else:
            logger.warning(f'User {self.email} not found in OKTA or is DEACTIVATED.')

    def soft_delete_user(self):
        user_from = self.organization.id if self.organization else 'STAFF'
        logger.info(
            f'Soft Deleting user {self.id} with email {self.email} '
            f'on organization: {user_from}'
        )
        self.deleted_at = timezone.now()
        self.is_active = False

    def __str__(self):
        organization = self.organization.name if self.organization else 'STAFF'
        return (
            f'{self.first_name} {self.last_name} ({organization})-deleted'
            if self.deleted_at
            else f'{self.first_name}             {self.last_name} ({organization})'
        )

    def save(self, *args, **kwargs):
        # TODO: Link User and LaikaObject models
        # Imported here to avoid circular imports
        update_fields = kwargs.get('update_fields')
        if update_fields and 'last_login' not in update_fields:
            from objects.utils import update_objects_with_user

            update_objects_with_user(self)
        self.email = self.email.lower() if self.email else ''
        super(User, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with reversion.create_revision():
            reversion.set_comment('User Deactivated')
            self.delete_from_identity_provider()
            self.soft_delete_user()
            super(User, self).save()

    def hard_delete(self):
        super(User, self).delete()

    def as_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'lastName': self.last_name,
            'firstName': self.first_name,
            'email': self.email,
        }

    @classmethod
    def map_employment_status(cls, value: bool) -> str:
        """
        Returns employment status choice using True or False as input
        """

        if value is True:
            return EMPLOYMENT_STATUS_ACTIVE
        elif value is False:
            return EMPLOYMENT_STATUS_INACTIVE
        else:
            return ''

    @property
    def all_pending_action_items(self):
        from action_item.constants import TYPE_CONTROL, TYPE_POLICY, TYPE_QUICK_START
        from action_item.models import ActionItem, ActionItemStatus

        action_items = ActionItem.objects.filter(
            assignees=self,
            status__in=[ActionItemStatus.NEW, ActionItemStatus.PENDING],
            metadata__type__in=[TYPE_QUICK_START, TYPE_CONTROL, TYPE_POLICY],
        )

        dashboard_items = self.action_item_assignee.filter(status=NOT_STARTED)

        return sorted(
            [*action_items, *dashboard_items],
            key=lambda action_item: action_item.due_date or datetime.now(timezone.utc),
        )

    def is_missing_mfa(self):
        if not self.organization:
            return False
        return not self.mfa and self.organization.is_flag_active(mfa_feature_flag)


@searchable_model(type='officer')
class Officer(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='officers'
    )
    description = models.TextField()
    name = models.CharField(max_length=100)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='officer', null=True, blank=True
    )

    def __str__(self):
        return self.name


@searchable_model(type='team')
class Team(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='teams'
    )
    description = models.TextField()
    name = models.CharField(max_length=100)
    charter = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


@reversion.register(follow=['team', 'user'])
class TeamMember(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=50, choices=MEMBER_ROLES)
    phone = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_member')

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name}'


auditor_help_text = '''
    First_name, last_name, email, role, password and username (email)
    are required when creating a new audit user.
    '''


class Auditor(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True, help_text=auditor_help_text
    )
    audit_firms = models.ManyToManyField(
        'audit.AuditFirm', related_name='auditors', through='audit.AuditorAuditFirm'
    )

    def __str__(self):
        return self.user.get_full_name()

    def save(self, *args, **kwargs):
        is_not_django = kwargs.get('is_not_django')

        # Execute only from Django Admin
        if self._state.adding and not is_not_django:
            # Circular dependency
            from .helpers import create_auditor_credentials

            try:
                user_data = {
                    'first_name': self.user.first_name,
                    'last_name': self.user.last_name,
                    'email': self.user.email,
                    'permission': self.user.role,
                }

                create_auditor_credentials(user_data)
            except Exception as e:
                logger.warning(
                    'There was a problem setting up auditor with'
                    f'id {self.user.id} credentials and invite. Error: {e}'
                )
                delete_cognito_users([self.user.email])

                raise ServiceException('Failed to create user credentials and invite')

        super(Auditor, self).save()


class Concierge(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='concierge',
        primary_key=True,
        help_text=concierge_help_text,
    )

    def __str__(self):
        return self.user.get_full_name()


class PartnerType(models.TextChoices):
    PENTEST = 'pentest'


class Partner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=128, choices=PartnerType.choices)
    calendar = models.TextField()
    users = models.ManyToManyField(
        User,
        related_name='partners',
        blank=True,
    )
    typeform = models.TextField(null=True)

    def __str__(self):
        return self.name


class WatcherList(models.Model):
    users = models.ManyToManyField(
        User,
        related_name='watchers',
        blank=True,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
    )
    name = models.TextField()

    def __str__(self):
        return self.name


class UserProxy(User):
    class Meta:
        proxy = True
        verbose_name = _('Soft Deleted User')
        verbose_name_plural = _('Soft Deleted Users')


def get_today():
    return timezone.now()


class MagicLink(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='magic_link',
    )
    updated_at = models.DateTimeField(auto_now=True)
    token = models.UUIDField(primary_key=True, default=uuid.uuid4)
    temporary_code = models.CharField(max_length=64)

    @property
    def is_otp_valid(self) -> bool:
        return get_today() < self.updated_at + timedelta(minutes=TWENTY_MINUTES)

    @property
    def otp_credentials(self) -> tuple[Optional[str], Optional[str]]:
        if not self.is_otp_valid:
            email = self.user.email
            self.delete()
            return email, None

        return self.user.email, self.temporary_code

    @property
    def temporary_credentials(self) -> tuple[Optional[str], Optional[str]]:
        # Cognito temporary password lifetime
        if get_today() > self.updated_at + timedelta(days=SEVEN_DAYS):
            email = self.user.email
            self.delete()
            return email, None
        return self.user.email, self.temporary_code


class UserAlert(models.Model):
    alert = models.ForeignKey(
        'alert.Alert', related_name='user_alert', on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, related_name='user_alerts', on_delete=models.CASCADE)
