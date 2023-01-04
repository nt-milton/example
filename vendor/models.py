from django.db import models

from alert.models import Alert
from certification.models import Certification
from evidence.models import Evidence
from laika.storage import PublicMediaStorage
from organization.models import Organization
from search.search import launchpad_model, searchable_model
from user.models import User
from vendor.utils import launchpad_mapper, search_vendor_qs

VENDOR_STATUS = [
    ('new', 'New'),
    ('requested', 'Requested'),
    ('review', 'In Review'),
    ('approved', 'Approved'),
    ('active', 'Active'),
    ('deprecated', 'Deprecated'),
    ('disqualified', 'Disqualified'),
]

DISCOVERY_STATUS_PENDING = 'pending'
DISCOVERY_STATUS_NEW = 'new'
DISCOVERY_STATUS_CONFIRMED = 'confirmed'
DISCOVERY_STATUS_IGNORED = 'ignored'
DISCOVERY_STATUS = [
    (DISCOVERY_STATUS_PENDING, 'Pending'),
    (DISCOVERY_STATUS_NEW, 'New'),
    (DISCOVERY_STATUS_CONFIRMED, 'Confirmed'),
    (DISCOVERY_STATUS_IGNORED, 'Ignored'),
]

ACTIVE_DISCOVERY_STATUSES = [DISCOVERY_STATUS_NEW, DISCOVERY_STATUS_IGNORED]
INACTIVE_DISCOVERY_STATUSES = [DISCOVERY_STATUS_PENDING, DISCOVERY_STATUS_CONFIRMED]

LOW_MEDIUM_HIGH = (('low', 'Low'), ('medium', 'Medium'), ('high', 'High'))

RISK_RATING_OPTIONS = (
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
)

DATA_EXPOSURE_OPTIONS = (
    ('no_sensitive_data', 'No sensitive data'),
    ('customer_pii', 'Customer PII'),
    ('employee_pii', 'Employee PII'),
    ('customer_and_employee_pii', 'Customer & Employee PII'),
    ('company_financial_data', 'Company Financial Data'),
)

ALERTS_USER_ROLES = ['OrganizationMember', 'OrganizationAdmin', 'SuperAdmin']


def certification_logo_directory_path(instance, filename):
    return f'certifications/{instance.name}/{filename}'


def vendor_logo_file_directory_path(instance, filename):
    return f'vendors/{instance.name}/{filename}'


def vendor_full_logo_file_directory_path(instance, filename):
    return f'vendors/{instance.name}/full_logo/{filename}'


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


@searchable_model(type='vendor', qs=search_vendor_qs, fields=['website'])
class Vendor(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255, unique=True)
    website = models.CharField(max_length=2000)
    logo = models.FileField(
        storage=PublicMediaStorage(),
        upload_to=vendor_logo_file_directory_path,
        max_length=1024,
        blank=True,
    )
    full_logo = models.FileField(
        storage=PublicMediaStorage(),
        upload_to=vendor_full_logo_file_directory_path,
        max_length=1024,
        blank=True,
    )
    description = models.TextField()
    is_public = models.BooleanField(default=False)
    organizations = models.ManyToManyField(
        Organization, related_name='vendors', through='OrganizationVendor'
    )

    categories = models.ManyToManyField(
        Category, related_name='vendors', through='VendorCategory'
    )

    certifications = models.ManyToManyField(
        Certification, related_name='vendors', through='VendorCertification'
    )

    def __str__(self):
        return self.name


class VendorCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.vendor.name


class VendorCandidate(models.Model):
    class Meta:
        unique_together = ('name', 'organization')

    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=DISCOVERY_STATUS, default='pending'
    )
    organization = models.ForeignKey(
        Organization,
        related_name='vendor_candidates',
        on_delete=models.CASCADE,
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, blank=True, null=True)
    number_of_users = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.name} - {self.organization}'


@launchpad_model(context='vendor', mapper=launchpad_mapper)
class OrganizationVendor(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='organization_vendors'
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=VENDOR_STATUS, default='new')
    financial_exposure = models.DecimalField(
        max_digits=19, decimal_places=2, default=0, blank=True
    )
    operational_exposure = models.CharField(
        max_length=6, choices=LOW_MEDIUM_HIGH, blank=True
    )
    data_exposure = models.CharField(
        max_length=27, choices=DATA_EXPOSURE_OPTIONS, blank=True
    )
    risk_rating = models.CharField(
        max_length=10, choices=RISK_RATING_OPTIONS, blank=True
    )
    purpose_of_the_solution = models.TextField(max_length=512, blank=True)
    additional_notes = models.TextField(max_length=512, blank=True)
    contract_start_date = models.TextField(max_length=512, blank=True)
    contract_renewal_date = models.TextField(max_length=512, blank=True)
    internal_stakeholders = models.ManyToManyField(
        User,
        related_name='stakeholder_vendors',
        through='OrganizationVendorStakeholder',
    )
    primary_external_stakeholder_name = models.CharField(
        max_length=100,
        blank=True,
    )
    primary_external_stakeholder_email = models.CharField(
        max_length=100,
        blank=True,
    )
    secondary_external_stakeholder_name = models.CharField(
        max_length=100,
        blank=True,
    )
    secondary_external_stakeholder_email = models.CharField(
        max_length=100,
        blank=True,
    )
    documents = models.ManyToManyField(
        Evidence,
        related_name='organization_vendor',
        through='OrganizationVendorEvidence',
    )
    risk_assessment_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f'{self.organization} - {self.vendor}'


class OrganizationVendorStakeholder(models.Model):
    sort_index = models.IntegerField()
    organization_vendor = models.ForeignKey(
        OrganizationVendor,
        on_delete=models.CASCADE,
        related_name='internal_organization_stakeholders',
    )
    stakeholder = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.stakeholder.get_full_name()}'


class OrganizationVendorEvidence(models.Model):
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE)
    organization_vendor = models.ForeignKey(
        OrganizationVendor,
        on_delete=models.CASCADE,
        related_name='organization_vendor_evidence',
    )

    def __str__(self):
        return str(self.evidence)


class VendorCertification(models.Model):
    certification = models.ForeignKey(Certification, on_delete=models.CASCADE)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name='vendor_certifications'
    )
    url = models.CharField(max_length=2000, blank=True)

    def __str__(self):
        return str(self.certification)


class VendorDiscoveryAlert(models.Model):
    quantity = models.IntegerField()
    alert = models.ForeignKey(
        Alert, related_name='vendor_alert', on_delete=models.CASCADE
    )
