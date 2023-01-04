import pytest

from audit.constants import AUDIT_FIRMS
from audit.models import AuditFirm, Organization
from audit.tests.factory import create_audit, create_audit_firm
from organization.tests import create_organization
from user.models import User
from user.tests import create_user

from ..models import Audit, Criteria, CriteriaRequirement, Requirement
from ..views import get_requirement_description_for_report


@pytest.fixture
def organization() -> Organization:
    return create_organization()


@pytest.fixture
def user(organization: Organization) -> User:
    return create_user(organization)


@pytest.fixture
def audit_firm() -> AuditFirm:
    return create_audit_firm(AUDIT_FIRMS[0])


@pytest.fixture
def audit(organization: Organization, audit_firm: AuditFirm) -> Audit:
    return create_audit(
        organization=organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=audit_firm,
    )


@pytest.fixture
def criteria() -> Criteria:
    return Criteria.objects.create(display_id='CC1.1', description='yyy')


@pytest.fixture
def requirement(audit: Audit) -> Requirement:
    return Requirement.objects.create(
        audit=audit, display_id='LCL-1', description='zzz'
    )


@pytest.fixture
def criteria_requirement(
    criteria: Criteria, requirement: Requirement
) -> CriteriaRequirement:
    return CriteriaRequirement.objects.create(
        criteria=criteria, requirement=requirement
    )


@pytest.mark.functional
@pytest.mark.parametrize(
    'display_id,description',
    [
        ('LCL-1', 'zzz'),
        ('LCL-2', ''),
    ],
)
def test_get_requirement_description_for_report(
    display_id: str,
    description: str,
    audit: Audit,
    requirement: Requirement,
):
    requirement_description = get_requirement_description_for_report(
        display_id, audit.id
    )
    assert requirement_description == description
