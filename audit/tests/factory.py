from datetime import datetime

from audit.constants import AUDIT_FRAMEWORK_TYPES, SOC_2_TYPE_2
from audit.models import (
    Audit,
    AuditAuditor,
    AuditFirm,
    AuditFrameworkType,
    AuditorAuditFirm,
    AuditStatus,
    OrganizationAuditFirm,
    UnlockedAuditFrameworkTypeOrganization,
)
from certification.tests import create_certification
from coupon.models import Coupon
from user.models import Auditor


def create_audit_firm(name):
    firm, _ = AuditFirm.objects.get_or_create(name=name)
    return firm


def get_framework_type_from_key(audit_type_key):
    audit_framework_type_dict = dict(AUDIT_FRAMEWORK_TYPES)
    return audit_framework_type_dict[audit_type_key]


def get_framework_key_from_value(audit_type):
    audit_framework_type_dict = dict(AUDIT_FRAMEWORK_TYPES)
    framework_key = [
        key for key, value in audit_framework_type_dict.items() if value == audit_type
    ]
    return framework_key[0]


def create_audit_framework_type(organization, audit_type_key, unlocked=True):
    audit_type = get_framework_type_from_key(audit_type_key)
    certification = create_certification(organization=organization, name=audit_type)
    audit_framework_type, _ = AuditFrameworkType.objects.get_or_create(
        certification=certification,
        audit_type=audit_type_key,
        description=f'{audit_type_key}',
    )
    if unlocked:
        UnlockedAuditFrameworkTypeOrganization.objects.get_or_create(
            organization=organization, audit_framework_type=audit_framework_type
        )
    return audit_framework_type


def create_coupon(organization, coupon_type, coupon_count=1):
    return Coupon.objects.create(
        organization=organization, type=coupon_type, coupons=coupon_count
    )


def create_audit(
    organization, name, audit_firm, audit_type='SOC 2 Type 1', is_completed=False
):
    audit_type_key = get_framework_key_from_value(audit_type)
    audit_framework_type = create_audit_framework_type(
        organization=organization, audit_type_key=audit_type_key
    )

    create_coupon(
        organization, coupon_type=f'{audit_type} {audit_firm.name}', coupon_count=1
    )

    audit = Audit.objects.create(
        organization=organization,
        name=name,
        audit_type=audit_type,
        audit_firm=audit_firm,
        audit_framework_type=audit_framework_type,
    )
    if is_completed:
        audit.completed_at = datetime.now()
        audit.save()

    return audit


def create_soc2_type2_audit(organization, audit_firm, audit_user):
    audit = create_audit(
        organization=organization,
        name='Laika Dev SOC 2 Type 2 Audit 2022',
        audit_firm=audit_firm,
        audit_type=SOC_2_TYPE_2,
    )
    audit.audit_configuration = {
        "as_of_date": '2022-08-18,2022-08-20',
        "trust_services_categories": ['Security', 'Availability', 'Process Integrity'],
    }
    audit.save()

    AuditAuditor.objects.create(audit=audit, auditor=audit_user.auditor)

    return audit


def create_audit_status(audit, **kwargs):
    return AuditStatus.objects.create(audit=audit, **kwargs)


def associate_organization_audit_firm(organization, audit_firm):
    return OrganizationAuditFirm.objects.create(
        organization=organization, audit_firm=audit_firm
    )


def link_auditor_to_audit_firm(audit_user, audit_firm):
    auditor = Auditor(user=audit_user)
    auditor.save(is_not_django=True)
    auditor.user.role = 'Auditor'
    auditor.user.save()
    AuditorAuditFirm.objects.create(auditor=auditor, audit_firm=audit_firm)
