import json

import pytest

from audit.models import AuditFeedbackReason
from audit.tests.queries import GET_AUDIT
from auditee.tests.mutations import ADD_AUDITEE_AUDIT_FEEDBACK


@pytest.mark.functional(permissions=['audit.add_auditfeedback'])
def test_add_audit_feedback(graphql_client, audit_soc2_type2):
    response = graphql_client.execute(
        ADD_AUDITEE_AUDIT_FEEDBACK,
        variables={
            "input": dict(
                auditId=audit_soc2_type2.id,
                rate=3.5,
                feedback='',
                reason=json.dumps(['Setting up my compliance program']),
            )
        },
    )

    feedback = response['data']['addAuditeeAuditFeedback']['feedback']
    user = graphql_client.context.get('user')

    assert feedback['id'] == str(audit_soc2_type2.id)
    assert feedback['user']['id'] == str(user.id)


@pytest.mark.functional(permissions=['audit.add_auditfeedback'])
def test_add_audit_feedback_update_if_exist(
    graphql_client, audit_soc2_type2, audit_feedback
):
    response = graphql_client.execute(
        ADD_AUDITEE_AUDIT_FEEDBACK,
        variables={
            "input": dict(
                auditId=audit_soc2_type2.id,
                rate=2,
                feedback='Test',
                reason=json.dumps(['Setting up my compliance program']),
            )
        },
    )

    feedback = response['data']['addAuditeeAuditFeedback']['feedback']

    assert feedback['rate'] == '2'
    assert feedback['feedback'] == 'Test'


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_return_audit_feedback_from_query(
    graphql_client, audit_soc2_type2, audit_feedback
):
    response = graphql_client.execute(
        GET_AUDIT,
        variables={
            'id': audit_soc2_type2.id,
        },
    )

    audit = response['data']['audit']

    assert audit['feedback']['rate'] == '3.0'
    assert audit['feedback']['feedback'] == audit_feedback.feedback


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_return_audit_feedback_reasons_from_query(graphql_client, audit_soc2_type2):
    AuditFeedbackReason.objects.create(
        audit_framework_type=audit_soc2_type2.audit_framework_type, reason='Service'
    )
    response = graphql_client.execute(
        GET_AUDIT,
        variables={
            'id': audit_soc2_type2.id,
        },
    )

    audit = response['data']['audit']

    assert audit['auditType']['feedbackReasons'] == ['Service']
