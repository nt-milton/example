from datetime import datetime

import pytest

from audit.models import AuditorAuditFirm
from auditor.tests.mutations import (
    ASSIGN_AUDITOR_REVIEWER_REQUIREMENT,
    ASSIGN_AUDITOR_TESTER_REQUIREMENT,
    CREATE_AUDITOR_REQUIREMENT,
    UPDATE_AUDITOR_REQUIREMENT,
    UPDATE_AUDITOR_REQUIREMENT_FIELD,
    UPDATE_AUDITOR_REQUIREMENTS_STATUS,
)
from auditor.tests.queries import GET_REQUIREMENTS
from auditor.utils import increment_display_id
from fieldwork.constants import REQ_STATUS_DICT
from fieldwork.models import Requirement, RequirementStatusTransition

ER_SUBMITTED_STATUS = 'submitted'


@pytest.fixture
def requirement_display_id_0(audit):
    return Requirement.objects.create(audit=audit, display_id='LCL-0', name='LCL-0')


@pytest.fixture
def auditor_audit_firm(graphql_audit_firm, graphql_audit_user):
    return AuditorAuditFirm.objects.create(
        audit_firm=graphql_audit_firm, auditor=graphql_audit_user.auditor
    )


@pytest.mark.functional(permissions=['fieldwork.view_requirement'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_requirements(graphql_audit_client, audit, requirement):
    response = graphql_audit_client.execute(
        GET_REQUIREMENTS,
        variables={
            'auditId': str(audit.id),
        },
    )
    requirement_data = response['data']['requirements']

    assert len(requirement_data) == 1


@pytest.mark.functional(permissions=['fieldwork.view_requirement'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_requirements_by_status(graphql_audit_client, audit, requirement):
    response = graphql_audit_client.execute(
        GET_REQUIREMENTS,
        variables={'auditId': str(audit.id), 'status': ER_SUBMITTED_STATUS},
    )
    requirement_data = response['data']['requirements']

    assert len(requirement_data) == 0


@pytest.mark.functional(permissions=['fieldwork.add_requirement'])
def test_create_requirement(
    graphql_audit_client,
    graphql_audit_user,
    auditor_audit_firm,
    audit,
    evidence,
    criteria,
):
    response = graphql_audit_client.execute(
        CREATE_AUDITOR_REQUIREMENT,
        variables={
            'input': {
                'auditId': str(audit.id),
                'name': 'Requirement',
                'language': 'one simple description',
                'relatedEvidence': ['1'],
                'relatedCriteria': ['1'],
            }
        },
    )

    requirement_data = response['data']['createAuditorRequirement']['requirement']

    requirement_created = Requirement.objects.get(
        audit=audit, display_id=requirement_data['displayId']
    )

    assert requirement_created.display_id == 'LCL-1'


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_update_auditor_requirement_field(
    graphql_audit_client,
    evidence,
    requirement,
):
    name_text = 'XXXX'

    assert requirement.last_edited_by is None
    assert requirement.last_edited_at is None

    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_FIELD,
        variables={
            'input': dict(
                auditId=str(evidence.audit.id),
                requirementId=str(requirement.id),
                field='name',
                value=name_text,
            )
        },
    )

    requirement = Requirement.objects.get(id=requirement.id)
    assert requirement.name == name_text
    assert requirement.last_edited_by is None
    assert requirement.last_edited_at is None


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_update_auditor_requirement_description(
    graphql_audit_client,
    graphql_audit_user,
    evidence,
    requirement,
):
    description_text = 'XXXX'

    assert requirement.last_edited_by is None
    assert requirement.last_edited_at is None

    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_FIELD,
        variables={
            'input': dict(
                auditId=str(evidence.audit.id),
                requirementId=str(requirement.id),
                field='description',
                value=description_text,
            )
        },
    )

    requirement = Requirement.objects.get(id=requirement.id)
    assert requirement.description == description_text
    assert requirement.last_edited_by == graphql_audit_user
    assert requirement.last_edited_at.strftime("%Y/%m/%d") == datetime.now().strftime(
        "%Y/%m/%d"
    )


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_update_auditor_requirement(
    graphql_audit_client,
    evidence,
    criteria,
    requirement,
):
    new_name = 'New name'
    new_description = 'New description'
    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT,
        variables={
            'input': dict(
                auditId=str(evidence.audit.id),
                requirementId=str(requirement.id),
                name=new_name,
                language=new_description,
                relatedEvidence=['1'],
                relatedCriteria=['1'],
            )
        },
    )

    requirement = Requirement.objects.get(id=requirement.id)
    assert requirement.name == new_name
    assert requirement.description == new_description


@pytest.mark.functional()
def test_increment_requirements_display_id(
    audit, requirement, requirement_display_id_0
):
    reference = 'LCL'
    increment = increment_display_id(Requirement, audit.id, reference)

    assert increment != 'LCL-1'
    assert increment == 'LCL-2'


@pytest.mark.functional()
def test_increment_empty_requirements_display_id(
    audit,
):
    reference = 'LCL'
    increment = increment_display_id(Requirement, audit.id, reference)

    assert increment == 'LCL-1'


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_track_times_moved_back_to_open_requirement(
    audit,
    requirement,
    completed_requirement,
    under_review_requirement,
    graphql_audit_client,
):
    assert completed_requirement.times_moved_back_to_open == 0
    assert under_review_requirement.times_moved_back_to_open == 0
    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENTS_STATUS,
        variables={
            'input': dict(
                ids=[
                    requirement.id,
                    completed_requirement.id,
                    under_review_requirement.id,
                ],
                status=REQ_STATUS_DICT['Open'],
                auditId=audit.id,
            )
        },
    )

    updated_requirement = Requirement.objects.get(id=requirement.id)
    updated_req_completed = Requirement.objects.get(id=completed_requirement.id)
    updated_req_under_review = Requirement.objects.get(id=under_review_requirement.id)

    assert updated_requirement.times_moved_back_to_open == 0
    assert updated_req_completed.times_moved_back_to_open == 1
    assert updated_req_under_review.times_moved_back_to_open == 1


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_requirement_status_transition_tester(
    audit,
    requirement,
    graphql_audit_client,
    graphql_audit_user,
):
    assert requirement.tester_updated_at is None
    graphql_audit_client.execute(
        ASSIGN_AUDITOR_TESTER_REQUIREMENT,
        variables={
            'input': dict(
                requirementIds=[
                    requirement.id,
                ],
                email=graphql_audit_user.email,
                auditId=audit.id,
            )
        },
    )
    updated_requirement = Requirement.objects.get(id=requirement.id)

    assert isinstance(updated_requirement.tester_updated_at, datetime) is True


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_requirement_status_transition_reviewer(
    audit,
    requirement,
    graphql_audit_client,
    graphql_audit_user,
):
    assert requirement.reviewer_updated_at is None
    graphql_audit_client.execute(
        ASSIGN_AUDITOR_REVIEWER_REQUIREMENT,
        variables={
            'input': dict(
                requirementIds=[
                    requirement.id,
                ],
                email=graphql_audit_user.email,
                auditId=audit.id,
            )
        },
    )
    updated_requirement = Requirement.objects.get(id=requirement.id)

    reviewer_updated_at = updated_requirement.reviewer_updated_at

    assert isinstance(reviewer_updated_at, datetime) is True


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_requirement_status_transition(
    audit, requirement, graphql_audit_client, graphql_audit_user
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENTS_STATUS,
        variables={
            'input': dict(
                ids=[
                    requirement.id,
                ],
                status=REQ_STATUS_DICT['Under Review'],
                auditId=audit.id,
            )
        },
    )
    Requirement.objects.get(id=requirement.id)
    requirement_status_transition = RequirementStatusTransition.objects.get(
        requirement=requirement
    )

    assert requirement_status_transition.status_updated_by == graphql_audit_user
    assert requirement_status_transition.from_status == REQ_STATUS_DICT['Open']
    assert requirement_status_transition.to_status == REQ_STATUS_DICT['Under Review']
