from audit.models import Audit
from auditor.utils import get_requirement_tests, get_requirements_by_args
from fieldwork.models import CriteriaRequirement


def get_requirements(audit: Audit):
    requirement_ids = (
        CriteriaRequirement.objects.filter(
            criteria__audit_id=audit.id,
            requirement__audit_id=audit.id,
            requirement__exclude_in_report=False,
        )
        .values_list('requirement_id', flat=True)
        .distinct()
    )

    requirements = (
        get_requirements_by_args(
            {
                'audit_id': audit.id,
            }
        )
        .filter(id__in=requirement_ids)
        .exclude(display_id='LCL-0')
    )

    evidence_requirements = [
        {
            'display_id': requirement.display_id,
            'description': requirement.description,
            'tests': get_requirement_tests(requirement),
        }
        for requirement in requirements
    ]
    return evidence_requirements
