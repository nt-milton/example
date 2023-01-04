import logging
import uuid
from datetime import datetime

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from pytz import timezone

from address.models import Address
from laika.settings import DJANGO_SETTINGS, ENVIRONMENT
from laika.storage import PrivateMediaStorage, PublicMediaStorage
from laika.utils.dates import get_future_date
from policy.constants import ONBOARDING_POLICIES
from user.constants import USER_ROLES

from .constants import (
    API_TOKEN_USAGE_TYPE,
    ARCHITECT_MEETING,
    AUTOMATE_COMPLIANCE,
    DATE_TIME_FORMAT,
    DEFAULT_API_TOKEN_USAGE_TYPE,
    EXPIRATION_PERIOD,
    ONBOARDING_READY,
    ONBOARDING_V2_STATE,
    QUESTIONNAIRE,
    US_EASTERN_TZ,
)
from .tasks import (
    configure_organization_initial_data,
    send_review_ready_email,
    send_review_starting_email,
)

logger = logging.getLogger(__name__)
USER_MODEL = 'user.User'

TIERS = [('PREMIUM', 'Premium')]

REPORT_FIELDS = [
    'name',
    'description',
    'website',
    'number_of_employees',
    'business_inception_date',
    'product_or_service_description',
    'logo',
]

ONBOARDING = 'ONBOARDING'
ACTIVE = 'ACTIVE'
TRIAL = 'TRIAL'
DEACTIVATED = 'DEACTIVATED'

PREMIUM = 'PREMIUM'

STATES = [
    (ONBOARDING, ONBOARDING),
    (ACTIVE, ACTIVE),
    (DEACTIVATED, DEACTIVATED),
    (TRIAL, TRIAL),
]


def organization_file_directory_path(organization, filename):
    return f'{organization.id}/metadata/{filename}'


def organization_offboarding_file_path(instance, filename):
    return f'{instance.checklist.organization.id}/offboarding/{filename}'


class Organization(models.Model):
    class Meta:
        permissions = [
            ('view_quick_links', 'Can view quick links'),
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    website = models.CharField(max_length=2000)
    logo = models.FileField(
        storage=PublicMediaStorage(),
        upload_to=organization_file_directory_path,
        max_length=2000,
    )
    customer_success_manager_user = models.ForeignKey(
        USER_MODEL,
        related_name='organization_csm',
        on_delete=models.SET_NULL,
        null=True,
    )
    compliance_architect_user = models.ForeignKey(
        USER_MODEL, related_name='organization_ca', on_delete=models.SET_NULL, null=True
    )
    sfdc_id = models.CharField(max_length=100)
    contract_sign_date = models.DateTimeField(null=True)
    description = models.TextField(blank=True, max_length=5000)

    tier = models.CharField(max_length=10, choices=TIERS, default=PREMIUM)
    state = models.CharField(max_length=20, choices=STATES, default=ONBOARDING)

    is_internal = models.BooleanField(default=False)
    is_public_company = models.BooleanField(null=True, blank=True)

    number_of_employees = models.IntegerField(null=True, blank=True)

    business_inception_date = models.DateField(null=True, blank=True)
    target_audit_date = models.DateTimeField(null=True, blank=True)

    product_or_service_description = models.TextField(blank=True, max_length=5000)
    billing_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        related_name='billing_address',
        null=True,
        blank=True,
    )

    audit_firms = models.ManyToManyField(
        'audit.AuditFirm',
        related_name='organizations',
        through='audit.OrganizationAuditFirm',
    )

    created_by = models.ForeignKey(
        USER_MODEL,
        related_name='organization_created_by',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    locations = models.ManyToManyField(
        Address, related_name='organizations', through='OrganizationLocation'
    )
    legal_name = models.CharField(max_length=200, blank=True)
    system_name = models.CharField(max_length=200, blank=True)

    calendly_url = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.name

    def is_flag_active(self, flag_name):
        return self.feature_flags.filter(name=flag_name, is_enabled=True).exists()

    def save(self, *args, **kwargs):
        if self._state.adding:
            super(Organization, self).save(*args, **kwargs)
            configure_organization_initial_data(self)

            if not Onboarding.objects.filter(organization=self).exists():
                logger.info(f'Init Onboarding for organization: {self.id}')
                init_onboarding(self)
        else:
            super(Organization, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        delete_organization_related_objects(self)
        super(Organization, self).delete(*args, **kwargs)

    def get_users(self, only_laika_users=False, exclude_super_admin=False):
        if only_laika_users:
            users = self.users.filter(is_active=True)
        else:
            users = self.users.all()

        if exclude_super_admin:
            return users.exclude(role=USER_ROLES['SUPER_ADMIN'])

        return users

    @property
    def unlocked_and_archived_unlocked_certs(self):
        unlocked_org_certs = self.unlocked_certifications.all()
        archived_unlocked_org_certs = self.archived_unlocked_certifications.all()
        return unlocked_org_certs.union(archived_unlocked_org_certs)


def delete_organization_related_objects(organization):
    from action_item.models import ActionItem  # avoid circular import

    ActionItem.objects.filter(metadata__organizationId=str(organization.id)).delete()

    logger.info('Trying to delete connection accounts')
    for ca in organization.connection_accounts.iterator():
        logger.info(f'Trying to delete connection account: {ca}')
        try:
            ca.delete()
            logger.info(f'Connection account: {ca} was successfully deleted')
        except Exception as e:
            logger.exception(f'Error deleting the connection: {e}')


class OrganizationChecklist(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    action_item = models.ForeignKey(
        'action_item.ActionItem', on_delete=models.CASCADE, related_name='checklist'
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    tags = models.ManyToManyField('tag.Tag', related_name='checklist_tags', blank=True)

    def __str__(self):
        return f'{self.action_item.name} ({self.organization.name})'


class OrganizationChecklistRun(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(
        USER_MODEL,
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        related_name='checklist_runs',
    )
    date = models.DateTimeField(null=False)
    document = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=organization_offboarding_file_path,
        blank=True,
        null=True,
        max_length=1024,
    )
    checklist = models.ForeignKey(
        OrganizationChecklist,
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        related_name='checklist_runs',
    )
    metadata = models.JSONField(blank=True, default=dict)

    def __str__(self):
        return f'{self.owner}'


class OffboardingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    NOT_APPLICABLE = 'not_applicable', 'Not Applicable'


class OffboardingVendor(models.Model):
    checklist_run = models.ForeignKey(
        OrganizationChecklistRun, on_delete=models.CASCADE, related_name='vendors'
    )
    vendor = models.ForeignKey('vendor.Vendor', on_delete=models.CASCADE)
    date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        blank=True,
        choices=OffboardingStatus.choices,
        default=OffboardingStatus.PENDING,
    )

    def __str__(self):
        return f'{self.checklist_run} - {self.vendor.name}'


class OrganizationChecklistRunSteps(models.Model):
    checklist_run = models.ForeignKey(
        OrganizationChecklistRun, on_delete=models.CASCADE, related_name='steps'
    )
    action_item = models.ForeignKey('action_item.ActionItem', on_delete=models.CASCADE)
    date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        blank=True,
        choices=OffboardingStatus.choices,
        default=OffboardingStatus.PENDING,
    )

    def __str__(self):
        return f'{self.checklist_run} - {self.action_item.description}'


def init_onboarding(organization):
    period_ends = get_future_date(EXPIRATION_PERIOD)
    onboarding = Onboarding.objects.create(
        organization=organization, period_ends=period_ends
    )

    for step in ONBOARDING_SETUP_STEP:
        OnboardingSetupStep.objects.create(
            onboarding=onboarding, name=step[1], completed=False
        )
    for onboarding_policy in ONBOARDING_POLICIES:
        organization.onboarding_policies.update_or_create(
            description=onboarding_policy[0]
        )


class OrganizationLocation(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name='organization_location',
    )
    name = models.CharField(max_length=255, blank=True)
    hq = models.BooleanField(default=False)

    def _increment_name(self):
        locations = OrganizationLocation.objects.filter(
            organization=self.organization
        ).order_by('-id')

        last_location = locations.first()
        try:
            _, key = last_location.name.split('-')

            new_key = int(key) + 1
        except Exception:
            new_key = locations.count() + 1

        self.name = f'Location-{new_key}'

    def save(self, *args, **kwargs):
        if self._state.adding and not self.name:
            self._increment_name()

        if self.hq:
            current_hq_location = OrganizationLocation.objects.filter(
                organization=self.organization, hq=True
            ).first()

            if current_hq_location:
                current_hq_location.hq = False
                current_hq_location.save()

        super(OrganizationLocation, self).save(*args, **kwargs)


ONBOARDING_STATES = [
    ('INIT', 'INIT'),
    ('ENROLLED', 'ENROLLED'),
    ('REVIEW', 'REVIEW'),
    ('READY', 'READY'),
    ('COMPLETED', 'COMPLETED'),
]


class Onboarding(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization,
        related_name='onboarding',
        on_delete=models.CASCADE,
    )
    state = models.CharField(max_length=50, choices=ONBOARDING_STATES, default='INIT')
    period_ends = models.DateField(null=True, blank=True)

    state_v2 = models.CharField(
        choices=ONBOARDING_V2_STATE, default=QUESTIONNAIRE, max_length=50
    )

    calendly_event_id_v2 = models.UUIDField(blank=True, null=True)
    calendly_invitee_id_v2 = models.UUIDField(blank=True, null=True)

    class Meta:
        permissions = [('super_onboarding', 'Can super access onboarding')]
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_states_valid",
                check=models.Q(state__in=[s[0] for s in ONBOARDING_STATES]),
            )
        ]

    def save(self, *args, **kwargs):
        super(Onboarding, self).save()
        handle_review_starting(self, kwargs.get('current_user'))


class OnboardingResponse(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization,
        related_name='onboarding_response',
        on_delete=models.CASCADE,
    )
    questionary_id = models.CharField(max_length=16)
    response_id = models.CharField(max_length=50, null=True, blank=True)
    questionary_response = models.JSONField(null=True, blank=True)

    submitted_by = models.ForeignKey(
        USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='onboarding_response',
    )

    class Meta:
        indexes = [GinIndex(fields=['questionary_response'])]


CONTROL_PRESCRIPTION = 'CONTROL_PRESCRIPTION'
DOCUMENTATION_REVIEW = 'DOCUMENTATION_REVIEW'
OPERATIONAL_MATURITY_REVIEW = 'OPERATIONAL_MATURITY_REVIEW'
SELECT_CERTIFICATIONS = 'SELECT_CERTIFICATIONS'
SEED_RELEVANT_DOCUMENTS = 'SEED_RELEVANT_DOCUMENTS'
ROADMAP_CONFIGURATION = 'ROADMAP_CONFIGURATION'

ONBOARDING_SETUP_STEP = [
    (CONTROL_PRESCRIPTION, CONTROL_PRESCRIPTION),
    (DOCUMENTATION_REVIEW, DOCUMENTATION_REVIEW),
    (OPERATIONAL_MATURITY_REVIEW, OPERATIONAL_MATURITY_REVIEW),
    (SELECT_CERTIFICATIONS, SELECT_CERTIFICATIONS),
    (SEED_RELEVANT_DOCUMENTS, SEED_RELEVANT_DOCUMENTS),
    (ROADMAP_CONFIGURATION, ROADMAP_CONFIGURATION),
]


class OnboardingSetupStep(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    onboarding = models.ForeignKey(
        Onboarding,
        related_name='setup_steps',
        on_delete=models.CASCADE,
    )
    completed = models.BooleanField(default=False)
    name = models.CharField(max_length=50, choices=ONBOARDING_SETUP_STEP)

    def save(self, *args, **kwargs):
        super(OnboardingSetupStep, self).save()
        if not self._state.adding:
            handle_review_ready(self.onboarding)

    def __str__(self):
        return f'{self.name}'.replace('_', ' ')


class CheckIn(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date = models.DateTimeField()
    organization = models.ForeignKey(
        Organization,
        related_name='check_ins',
        on_delete=models.CASCADE,
    )
    cx_participant = models.ForeignKey(
        USER_MODEL, related_name='check_ins', on_delete=models.CASCADE
    )
    customer_participant = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField()
    action_items = models.TextField()
    active = models.BooleanField(default=True)


class ApiTokenHistoryManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.all_records = kwargs.pop('all_records', False)
        super(models.Manager, self).__init__(*args, **kwargs)

    def get_queryset(self):
        if self.all_records:
            return super().get_queryset()
        return super().get_queryset().filter(usage_type=DEFAULT_API_TOKEN_USAGE_TYPE)


class ApiTokenHistory(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'token_identifier'],
                name='unique_token_for_organization',
            )
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    name = models.TextField()
    api_key = models.TextField()
    # We will use this value to identify the token
    # and revoke the token with this ID
    token_identifier = models.UUIDField(blank=False, null=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='api_tokens'
    )
    created_by = models.ForeignKey(
        USER_MODEL,
        related_name='api_tokens',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    usage_type = models.CharField(
        max_length=50,
        choices=API_TOKEN_USAGE_TYPE,
        blank=True,
        default=DEFAULT_API_TOKEN_USAGE_TYPE,
    )

    objects = ApiTokenHistoryManager()
    all_objects = ApiTokenHistoryManager(all_records=True)

    def __str__(self):
        return self.name


def handle_review_starting(onboarding, current_user):
    if is_review_starting(onboarding):
        organization = onboarding.organization
        cx_support_email = DJANGO_SETTINGS.get('CX_SUPPORT_EMAIL')

        user_emails = []
        if cx_support_email:
            user_emails.append(cx_support_email)

        if organization.customer_success_manager_user:
            user_emails.append(organization.customer_success_manager_user.email)
        if organization.compliance_architect_user:
            user_emails.append(organization.compliance_architect_user.email)

        if user_emails:
            now = datetime.now(timezone(US_EASTERN_TZ))
            start_date = f'{now.strftime(DATE_TIME_FORMAT)} (EST)'
            user_name = 'Not Available'
            if current_user:
                user_name = f'{current_user.first_name} {current_user.last_name}'

            template_context = {
                'user_name': user_name,
                'organization_name': organization.name,
                'start_date': start_date,
            }

            send_review_starting_emails(user_emails, template_context)


def send_review_starting_emails(user_emails: list[str], template_context: dict):
    send_review_starting_email.delay(user_emails, template_context)


def is_review_starting(onboarding):
    return onboarding.state == 'REVIEW' and not any(steps_status(onboarding))


def handle_review_ready(onboarding):
    if is_review_v1_ready(onboarding) or is_review_v2_ready(onboarding):
        onboarding.state = ONBOARDING_READY
        onboarding.state_v2 = ONBOARDING_READY
        onboarding.save(update_fields=['state'])

        user_emails = list(
            onboarding.organization.users.filter(
                role__contains='Admin', is_active=True
            ).values_list('email', flat=True)
        )

        if ENVIRONMENT != 'local':
            user_emails.append(DJANGO_SETTINGS.get('CX_SUPPORT_EMAIL'))

        send_review_ready_email(user_emails)


def is_review_v1_ready(onboarding):
    return onboarding.state == 'REVIEW' and all(steps_status(onboarding))


def is_review_v2_ready(onboarding):
    return (
        onboarding.state_v2 == ARCHITECT_MEETING
        or onboarding.state_v2 == AUTOMATE_COMPLIANCE
    ) and all(steps_status(onboarding))


def steps_status(onboarding):
    return [step.completed for step in onboarding.setup_steps.all()]


class SubtaskTag(models.Model):
    subtask_text = models.TextField()
    tags = models.TextField()
