import pytest

from audit.models import (
    AuditFeedback,
    AuditFeedbackReason,
    AuditFrameworkType,
    AuditStatus,
)
from audit.tests.constants import SOC_2_TYPE_1
from coupon.models import Coupon

from .factory import create_audit, get_framework_type_from_key


@pytest.fixture
def audit_soc_2_type_1(graphql_organization, graphql_user, graphql_audit_firm):
    return create_audit(
        organization=graphql_organization,
        name='Test audit Soc 2 2021',
        audit_firm=graphql_audit_firm,
    )


@pytest.mark.functional()
def test_audit_coupons(graphql_organization, audit_soc_2_type_1, graphql_audit_firm):
    framework_type = get_framework_type_from_key(SOC_2_TYPE_1)
    coupon = Coupon.objects.get(
        organization=graphql_organization,
        type=f'{framework_type} {graphql_audit_firm.name}',
    )

    assert coupon.coupons == 0


@pytest.mark.functional()
@pytest.mark.parametrize(
    'initial_value, is_document_complete, expected',
    [
        (True, True, True),
        (False, True, True),
        (False, False, False),
        (True, False, False),
    ],
)
def test_audit_status_update_check_field(
    audit_status: AuditStatus, initial_value, is_document_complete, expected
):
    audit_status.subsequent_events_questionnaire_checked = initial_value
    audit_status.save()

    audit_status.update_check_field(
        'subsequent_events_questionnaire_checked', is_document_complete
    )

    assert (
        AuditStatus.objects.get(
            id=audit_status.id
        ).subsequent_events_questionnaire_checked
        is expected
    )


@pytest.mark.functional()
def test_save_audit_feedback_reason(audit_framework_soc_2_type_1):
    reasons = [
        'Setting up my compliance program (implementing controls)',
        'During the audit (evidence collection)',
        'Service',
        'Other',
    ]
    AuditFeedbackReason.objects.bulk_create(
        [
            AuditFeedbackReason(
                audit_framework_type=audit_framework_soc_2_type_1, reason=reason
            )
            for reason in reasons
        ]
    )

    assert AuditFrameworkType.objects.get(
        id=audit_framework_soc_2_type_1.id
    ).feedback_reason.count() == len(reasons)


@pytest.mark.functional()
def test_save_audit_feedback(audit_soc2_type1):
    feedback = 'setting up my compliance program was difficult'
    AuditFeedback.objects.create(
        audit=audit_soc2_type1,
        rate=3.5,
        feedback=feedback,
        reason=['Setting up my compliance program', 'Service'],
    )
    audit_feedback = AuditFeedback.objects.get(audit_id=audit_soc2_type1.id)
    assert audit_feedback.rate == 3.5
    assert audit_feedback.feedback == feedback
