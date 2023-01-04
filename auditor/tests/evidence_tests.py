import tempfile

import pytest
from django.core.files import File

from audit.constants import AUDIT_FIRMS, TITLE_ROLES
from audit.models import AuditAuditor, AuditorAuditFirm
from audit.tests.factory import (
    create_audit,
    create_audit_firm,
    link_auditor_to_audit_firm,
)
from fieldwork.constants import ER_STATUS_DICT
from fieldwork.models import (
    Attachment,
    Evidence,
    EvidenceComment,
    Requirement,
    RequirementEvidence,
    Test,
)
from fieldwork.tests.utils_tests import (
    create_evidence_attachment,
    multiline_to_singleline,
)
from fieldwork.types import EvidenceCommentPoolsEnum
from user.constants import AUDITOR
from user.models import Auditor
from user.tests.factory import create_user_auditor

from .mutations import (
    ADD_AUDITOR_EVIDENCE_ATTACHMENT,
    ADD_AUDITOR_EVIDENCE_REQUEST,
    ASSIGN_AUDITOR_REVIEWER_REQUIREMENT,
    ASSIGN_AUDITOR_TESTER_REQUIREMENT,
    ASSIGN_EVIDENCE,
    DELETE_AUDIT_EVIDENCE,
    DELETE_AUDITOR_ALL_EVIDENCE_ATTACHMENTS,
    DELETE_AUDITOR_EVIDENCE_ATTACHMENT,
    DELETE_AUDITOR_REQUIREMENT,
    RENAME_AUDITOR_EVIDENCE_ATTACHMENT,
    UPDATE_AUDITOR_EVIDENCE_REQUEST,
    UPDATE_AUDITOR_EVIDENCE_STATUS,
    UPDATE_AUDITOR_REQUIREMENTS_STATUS,
    UPDATE_EVIDENCE,
)
from .queries import (
    GET_ACCEPTED_EVIDENCE_COUNT,
    GET_ALL_EVIDENCE,
    GET_AUDITOR_ALL_REQUIREMENTS,
    GET_AUDITOR_AUDIT_EVIDENCE,
    GET_AUDITOR_EVIDENCE_COMMENTS_BY_POOL,
    GET_AUDITOR_EVIDENCE_DETAILS,
    GET_AUDITOR_REQUIREMENT,
    GET_NEW_AUDITOR_EVIDENCE_REQUEST_DISPLAY_ID,
    GET_REQUIREMENT_USERS,
)

ER_OPEN_STATUS = 'open'
ER_ACCEPTED_STATUS = 'auditor_accepted'


@pytest.fixture
def laika_audit_firm():
    return create_audit_firm(AUDIT_FIRMS[0])


@pytest.fixture
def laika_audit(graphql_organization, laika_audit_firm):
    return create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=laika_audit_firm,
    )


@pytest.fixture
def evidence(graphql_organization, audit):
    evidence = Evidence.objects.create(
        audit=audit,
        display_id='ER-1',
        name='Ev1',
        instructions='yyyy',
        status=ER_OPEN_STATUS,
    )
    create_evidence_attachment(graphql_organization, evidence)

    return evidence


@pytest.fixture
def evidence_attachment(audit, evidence):
    return Attachment.objects.create(name='Evidence Attachment', evidence=evidence)


@pytest.fixture
def evidence_attachment_deleted(audit, evidence):
    return Attachment.objects.create(
        name='attachment_rename.pdf', evidence=evidence, is_deleted=True
    )


@pytest.fixture
def laika_requirement_with_test(laika_audit):
    requirement = Requirement.objects.create(
        audit=laika_audit, display_id='LCL-2', status='under_review'
    )
    Test.objects.create(
        display_id='T1',
        name='Test1',
        result='exceptions_noted',
        requirement=requirement,
    )
    return requirement


@pytest.fixture
def requirement_with_complete_test(audit):
    requirement = Requirement.objects.create(
        audit=audit, display_id='LCL-3', status='under_review'
    )
    Test.objects.create(
        display_id='T4',
        name='Test4',
        result='exceptions_noted',
        notes='Notes',
        requirement=requirement,
    )
    Test.objects.create(
        display_id='T5',
        name='Test6',
        result='not_tested',
        notes='Notes',
        requirement=requirement,
    )
    Test.objects.create(
        display_id='T6',
        name='Test6',
        result='no_exceptions_noted',
        requirement=requirement,
    )
    return requirement


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_auditor_all_evidence(graphql_audit_client, evidence, audit):
    response = graphql_audit_client.execute(
        GET_ALL_EVIDENCE, variables={'auditId': str(audit.id), 'status': 'Open'}
    )
    assert len(response['data']['auditorAllEvidence']) == 1


@pytest.mark.functional(permissions=['fieldwork.assign_evidence'])
def test_assign_user_evidence_with_not_allowed_role(
    graphql_audit_client, graphql_audit_user, evidence
):
    assign_evidence_input = {
        'input': dict(
            evidenceIds=[str(evidence.id)],
            email=graphql_audit_user.email,
            auditId=evidence.audit.id,
        )
    }

    response = graphql_audit_client.execute(
        ASSIGN_EVIDENCE, variables=assign_evidence_input
    )

    expected_error = '''
    Only roles ['SuperAdmin', 'OrganizationAdmin']can assign
    a user to evidence'''
    assert multiline_to_singleline(
        response['errors'][0]['message']
    ) == multiline_to_singleline(expected_error)
    assert response['data']['assignAuditorEvidence'] is None


@pytest.mark.functional(permissions=['fieldwork.assign_evidence'])
def test_assign_user_evidence_with_allowed_role(
    graphql_audit_client, graphql_audit_user, evidence
):
    graphql_audit_user.role = 'SuperAdmin'
    graphql_audit_user.save()
    assign_evidence_input = {
        'input': dict(
            evidenceIds=[str(evidence.id)],
            email=graphql_audit_user.email,
            auditId=evidence.audit.id,
        )
    }

    response = graphql_audit_client.execute(
        ASSIGN_EVIDENCE, variables=assign_evidence_input
    )

    assign_user_data = response['data']['assignAuditorEvidence']

    assert assign_user_data['assigned'][0] == str(evidence.id)


@pytest.mark.functional(permissions=['fieldwork.view_evidencecomment'])
def test_get_auditor_evidence_comments_by_pool(
    graphql_audit_client, graphql_audit_user, evidence
):
    EvidenceComment.objects.custom_create(
        owner=graphql_audit_user,
        evidence_id=evidence.id,
        tagged_users=[],
        content='New Comment',
        is_internal_comment=True,
        pool=EvidenceCommentPoolsEnum.LCL.value,
    )
    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENTS_BY_POOL,
        variables={
            'auditId': evidence.audit.id,
            'evidenceId': evidence.id,
            'pool': EvidenceCommentPoolsEnum.LCL.name,
        },
    )
    assert len(response['data']['auditorEvidenceComments']) == 1


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_fieldwork_auditor_evidence(
    graphql_audit_client, graphql_audit_user, audit, evidence
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_DETAILS,
        variables={'auditId': str(audit.id), 'evidenceId': str(evidence.id)},
    )

    evidence_id = response['data']['auditorEvidence']['id']
    assert evidence_id == '1'


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_fieldwork_auditor_evidence_as_auditor(
    graphql_audit_client, graphql_audit_user, audit, evidence
):
    title_roles = dict(TITLE_ROLES)
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()

    auditor = Auditor.objects.get(user=graphql_audit_user)

    AuditAuditor.objects.create(
        audit=audit, auditor=auditor, title_role=title_roles['tester']
    )

    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_DETAILS,
        variables={'auditId': str(audit.id), 'evidenceId': str(evidence.id)},
    )

    evidence_id = response['data']['auditorEvidence']['id']
    assert evidence_id == '1'


@pytest.mark.functional(permissions=['fieldwork.view_requirement'])
def test_fieldwork_auditor_requirement(
    graphql_audit_client, graphql_audit_user, audit, requirement
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_REQUIREMENT,
        variables={'auditId': str(audit.id), 'requirementId': str(requirement.id)},
    )

    requirement_id = response['data']['requirement']['id']
    assert requirement_id == '1'


@pytest.mark.functional(permissions=['fieldwork.view_requirement'])
def test_fieldwork_auditor_requirement_as_auditor(
    graphql_audit_client, graphql_audit_user, audit, requirement
):
    title_roles = dict(TITLE_ROLES)
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()

    AuditAuditor.objects.create(
        audit=audit,
        auditor=graphql_audit_user.auditor,
        title_role=title_roles['tester'],
    )

    response = graphql_audit_client.execute(
        GET_AUDITOR_REQUIREMENT,
        variables={'auditId': str(audit.id), 'requirementId': str(requirement.id)},
    )

    requirement_id = response['data']['requirement']['id']
    assert requirement_id == '1'


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_fieldwork_accepted_evidence_count(graphql_audit_client, audit, evidence):
    evidence.status = ER_ACCEPTED_STATUS
    evidence.save()
    response = graphql_audit_client.execute(
        GET_ACCEPTED_EVIDENCE_COUNT, variables={'auditId': str(audit.id)}
    )

    results = response["data"]["auditorAcceptedEvidenceCount"]
    assert results['acceptedEvidence'] == 1


@pytest.mark.functional(permissions=['fieldwork.view_requirement'])
def test_auditor_all_requirements(graphql_audit_client, audit):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ALL_REQUIREMENTS, variables={'auditId': str(audit.id)}
    )

    requirement_data = response['data']['auditorAllRequirements']

    assert len(requirement_data) == 1


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_fieldwork_audit_evidence(graphql_audit_client, evidence, audit):
    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_EVIDENCE,
        variables={'auditId': str(audit.id), 'status': 'Open'},
    )
    assert len(response['data']['auditorAuditEvidence']) == 1


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_requirement_audit_users(
    graphql_audit_client,
    graphql_organization,
    graphql_audit_user,
    graphql_audit_firm,
    audit,
):
    graphql_audit_user.role = 'AuditorAdmin'
    graphql_audit_user.save()

    auditor_admin_not_in_audit = create_user_auditor(
        email="test1@heylaika.com", role='AuditorAdmin'
    )
    auditor = create_user_auditor(email="test2@heylaika.com", role='Auditor')
    auditor_admin_in_audit = create_user_auditor(
        email="test3@heylaika.com", role='AuditorAdmin'
    )

    AuditorAuditFirm.objects.create(
        auditor=auditor_admin_not_in_audit, audit_firm=graphql_audit_firm
    )
    AuditorAuditFirm.objects.create(auditor=auditor, audit_firm=graphql_audit_firm)
    AuditorAuditFirm.objects.create(
        auditor=auditor_admin_in_audit, audit_firm=graphql_audit_firm
    )
    AuditorAuditFirm.objects.create(
        auditor=graphql_audit_user.auditor, audit_firm=graphql_audit_firm
    )

    AuditAuditor.objects.create(audit=audit, auditor=auditor_admin_in_audit)

    response = graphql_audit_client.execute(
        GET_REQUIREMENT_USERS, variables={'auditId': str(audit.id)}
    )

    assert len(response['data']['requirementAuditUsers']) == 3


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_assign_auditor_tester_requirement(
    graphql_audit_client, evidence, requirement, graphql_audit_user
):
    assert not requirement.tester

    graphql_audit_client.execute(
        ASSIGN_AUDITOR_TESTER_REQUIREMENT,
        variables={
            'input': dict(
                auditId=str(evidence.audit.id),
                requirementIds=[requirement.id],
                email=graphql_audit_user.email,
            )
        },
    )

    requirement = Requirement.objects.get(id=requirement.id)
    assert requirement.tester.user.email == graphql_audit_user.email

    graphql_audit_client.execute(
        ASSIGN_AUDITOR_TESTER_REQUIREMENT,
        variables={
            'input': dict(
                auditId=str(evidence.audit.id),
                requirementIds=[requirement.id],
                email='',
            )
        },
    )

    requirement = Requirement.objects.get(id=requirement.id)
    assert not requirement.tester


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_assign_auditor_reviewer_requirement(
    graphql_audit_client, evidence, requirement, graphql_audit_firm, graphql_audit_user
):
    link_auditor_to_audit_firm(graphql_audit_user, graphql_audit_firm)

    assert not requirement.reviewer

    graphql_audit_client.execute(
        ASSIGN_AUDITOR_REVIEWER_REQUIREMENT,
        variables={
            'input': dict(
                auditId=str(evidence.audit.id),
                requirementIds=[requirement.id],
                email=graphql_audit_user.email,
            )
        },
    )

    requirement = Requirement.objects.get(id=requirement.id)
    assert requirement.reviewer.user.email == graphql_audit_user.email

    graphql_audit_client.execute(
        ASSIGN_AUDITOR_REVIEWER_REQUIREMENT,
        variables={
            'input': dict(
                auditId=str(evidence.audit.id),
                requirementIds=[requirement.id],
                email='',
            )
        },
    )

    requirement = Requirement.objects.get(id=requirement.id)
    assert not requirement.reviewer


@pytest.mark.functional(permissions=['fieldwork.delete_evidence'])
def test_delete_audit_evidence(graphql_audit_client, requirement, evidence):
    RequirementEvidence.objects.create(evidence=evidence, requirement=requirement)
    delete_audit_evidence_input = {
        'input': dict(evidenceIds=[str(evidence.id)], auditId=evidence.audit.id)
    }
    response = graphql_audit_client.execute(
        DELETE_AUDIT_EVIDENCE, variables=delete_audit_evidence_input
    )

    evidence = Evidence.objects.get(id=evidence.id)
    requirement_evidence = RequirementEvidence.objects.filter(evidence_id=evidence.id)
    assert evidence.is_deleted
    assert len(requirement_evidence) == 0
    assert response['data']['deleteAuditEvidence']['deleted'] == [str(evidence.id)]


@pytest.mark.functional(permissions=['fieldwork.delete_requirement'])
def test_delete_auditor_requirement(graphql_audit_client, evidence, requirement):
    RequirementEvidence.objects.create(evidence=evidence, requirement=requirement)

    delete_audit_requirement_input = {
        'input': dict(
            requirementIds=[str(requirement.id)], auditId=requirement.audit.id
        )
    }
    graphql_audit_client.execute(
        DELETE_AUDITOR_REQUIREMENT, variables=delete_audit_requirement_input
    )

    requirement = Requirement.objects.get(id=requirement.id)
    requirement_evidence = RequirementEvidence.objects.filter(
        requirement_id=requirement.id
    )
    assert requirement.is_deleted
    assert len(requirement_evidence) == 0


@pytest.mark.functional(permissions=['fieldwork.add_evidence_attachment'])
def test_add_evidence_attachment_auditor(
    graphql_audit_client, graphql_audit_user, evidence
):
    file = File(file=tempfile.TemporaryFile(), name='File Name')

    add_attachment_input_auditor = {
        'input': dict(
            id=str(evidence.id),
            uploadedFiles=[dict(fileName=file.name, file='test')],
            policies=[],
            documents=[],
            timeZone='UTC',
            officers=[],
            teams=[],
            vendors=[],
            trainings=[],
        )
    }
    response_audits = graphql_audit_client.execute(
        ADD_AUDITOR_EVIDENCE_ATTACHMENT, variables=add_attachment_input_auditor
    )
    ids = response_audits["data"]["addAuditorEvidenceAttachment"]["documentIds"]
    assert len(ids) == 1


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_evidence_status_open_accepted(
    graphql_audit_client,
    graphql_audit_user,
    audit,
    evidence,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[evidence.id], status='AuditorAccepted', auditId=evidence.audit.id
            )
        },
    )

    assert response['data']['updateAuditorEvidenceStatus']['updated'][0] == str(
        evidence.id
    )


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_rename_auditor_evidence_attachment(
    graphql_audit_client,
    graphql_audit_user,
    evidence,
    evidence_attachment,
    graphql_audit_firm,
):
    rename_attachment_input = {
        'input': dict(
            attachmentId=str(evidence_attachment.id),
            evidenceId=evidence.id,
            newName="new test name.pdf",
        )
    }

    link_auditor_to_audit_firm(graphql_audit_user, graphql_audit_firm)
    response = graphql_audit_client.execute(
        RENAME_AUDITOR_EVIDENCE_ATTACHMENT, variables=rename_attachment_input
    )
    assert response['data']['renameAuditorEvidenceAttachment']['updated'] == str(
        evidence_attachment.id
    )


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_rename_auditor_evidence_attachment_deleted(
    graphql_audit_client,
    graphql_audit_user,
    evidence,
    evidence_attachment,
    evidence_attachment_deleted,
    graphql_audit_firm,
):
    new_attachment_name = "attachment_rename.pdf"
    rename_attachment_input = {
        'input': dict(
            attachmentId=str(evidence_attachment.id),
            evidenceId=evidence.id,
            newName=new_attachment_name,
        )
    }

    link_auditor_to_audit_firm(graphql_audit_user, graphql_audit_firm)
    graphql_audit_client.execute(
        RENAME_AUDITOR_EVIDENCE_ATTACHMENT, variables=rename_attachment_input
    )

    renamed_attachment = Attachment.objects.get(id=evidence_attachment.id)
    assert renamed_attachment.name == new_attachment_name


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_update_auditor_requirements_status(graphql_audit_client, requirement):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENTS_STATUS,
        variables={
            'input': dict(
                ids=['1'], status='under_review', auditId=requirement.audit.id
            )
        },
    )
    assert (
        Requirement.objects.get(display_id=requirement.display_id).status
        == 'under_review'
    )


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_mark_requirement_completed_not_in_firm(
    graphql_audit_client, laika_requirement_with_test
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENTS_STATUS,
        variables={
            'input': dict(
                ids=[laika_requirement_with_test.id],
                status='completed',
                auditId=laika_requirement_with_test.audit.id,
            )
        },
    )

    formatted_response = multiline_to_singleline(response['errors'][0]['message'])
    expected_response = multiline_to_singleline(
        """
        Requirements can only be marked as complete
        by a member of the Audit Firm
        """
    )

    assert formatted_response == expected_response


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_mark_requirement_completed_not_reviewer_lead_or_admin(
    graphql_audit_client, graphql_audit_user, requirement_with_test
):
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()

    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENTS_STATUS,
        variables={
            'input': dict(
                ids=[requirement_with_test.id],
                status='completed',
                auditId=requirement_with_test.audit.id,
            )
        },
    )

    formatted_response = multiline_to_singleline(response['errors'][0]['message'])
    expected_response = multiline_to_singleline(
        """
        Requirements can only be marked as complete by a
        Reviewer, Lead Auditor or Admin
        """
    )

    assert formatted_response == expected_response


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_mark_requirement_completed_missing_notes(
    graphql_audit_client, graphql_audit_user, requirement_with_test
):
    AuditAuditor.objects.create(
        audit=requirement_with_test.audit,
        auditor=graphql_audit_user.auditor,
        title_role='reviewer',
    )

    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENTS_STATUS,
        variables={
            'input': dict(
                ids=[requirement_with_test.id],
                status='completed',
                auditId=requirement_with_test.audit.id,
            )
        },
    )

    formatted_response = multiline_to_singleline(response['errors'][0]['message'])

    expected_response = multiline_to_singleline(
        f'''{requirement_with_test.display_id}: Tests with Exceptions Noted or
        Not Tested must have notes'''
    )

    assert formatted_response == expected_response


@pytest.mark.functional(permissions=['fieldwork.change_requirement'])
def test_mark_requirement_completed(
    graphql_audit_client, graphql_audit_user, requirement_with_complete_test
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENTS_STATUS,
        variables={
            'input': dict(
                ids=[requirement_with_complete_test.id],
                status='completed',
                auditId=requirement_with_complete_test.audit.id,
            )
        },
    )

    assert response['data']['updateAuditorRequirementsStatus']['updated'] == [
        str(requirement_with_complete_test.id)
    ]


@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_auditor_evidence_attachment(
    graphql_audit_client,
    graphql_audit_user,
    evidence,
    evidence_attachment,
    graphql_audit_firm,
):
    delete_attachment_input = {
        'input': dict(
            attachmentId=str(evidence_attachment.id),
            evidenceId=evidence.id,
            auditId=evidence.audit.id,
        )
    }

    link_auditor_to_audit_firm(graphql_audit_user, graphql_audit_firm)
    response = graphql_audit_client.execute(
        DELETE_AUDITOR_EVIDENCE_ATTACHMENT, variables=delete_attachment_input
    )

    assert response['data']['deleteAuditorEvidenceAttachment']['attachmentId'] == str(
        evidence_attachment.id
    )
    updated_attach = Attachment.objects.get(id=evidence_attachment.id)
    assert updated_attach.deleted_by.id == graphql_audit_user.id


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_tester_for_evidence(
    graphql_audit_client, requirement_with_test, requirement, evidence, auditor_user
):
    requirement.tester = auditor_user
    requirement.save()
    RequirementEvidence.objects.create(evidence=evidence, requirement=requirement)
    RequirementEvidence.objects.create(
        evidence=evidence, requirement=requirement_with_test
    )
    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_DETAILS,
        variables={'auditId': evidence.audit.id, 'evidenceId': evidence.id},
    )
    assert response['data']['auditorEvidence']['tester']['id'] == auditor_user.user.id


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_store_evidence_status_transitions_with_same_status(
    graphql_audit_client, evidence
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[str(evidence.id)], status='Open', auditId=evidence.audit.id
            )
        },
    )

    evidence = Evidence.objects.get(id=evidence.id)
    evidence_transitions_count = evidence.status_transitions.all().count()

    assert evidence_transitions_count == 0


ER_SUBMITTED_STATUS = 'submitted'


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_store_evidence_status_transitions_with_different_status(
    graphql_audit_client, evidence
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[str(evidence.id)], status='Submitted', auditId=evidence.audit.id
            )
        },
    )

    evidence = Evidence.objects.get(id=evidence.id)
    evidence_transitions = evidence.status_transitions.all()
    transition = evidence_transitions[0]

    assert evidence_transitions.count() == 1
    assert transition.from_status == ER_OPEN_STATUS
    assert transition.to_status == ER_SUBMITTED_STATUS
    assert transition.created_at is not None


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_store_evidence_status_transition(graphql_audit_client, audit, evidence):
    graphql_audit_client.execute(
        UPDATE_EVIDENCE,
        variables={
            'input': dict(
                auditId=str(audit.id), evidenceId=str(evidence.id), status='Submitted'
            )
        },
    )

    evidence = Evidence.objects.get(id=evidence.id)
    evidence_transitions = evidence.status_transitions.all()
    transition = evidence_transitions[0]
    assert evidence_transitions.count() == 1
    assert transition.from_status == ER_OPEN_STATUS
    assert transition.to_status == ER_SUBMITTED_STATUS
    assert transition.created_at is not None


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_evidence_status_to_open(
    graphql_audit_client, graphql_audit_user, audit, evidence
):
    evidence.status = ER_ACCEPTED_STATUS
    evidence.is_laika_reviewed = True
    evidence.save()

    transition_reasons = 'Incorrect evidence, Missing evidence'
    extra_notes = 'some evidence are incomplete'

    graphql_audit_client.execute(
        UPDATE_EVIDENCE,
        variables={
            'input': dict(
                auditId=str(audit.id),
                evidenceId=str(evidence.id),
                status='Open',
                transitionReasons=transition_reasons,
                extraNotes=extra_notes,
            )
        },
    )

    updated_evidence = Evidence.objects.get(id=evidence.id)

    er_transition = updated_evidence.status_transitions.first()
    assert er_transition.transition_reasons == transition_reasons
    assert er_transition.extra_notes == extra_notes
    assert er_transition.transitioned_by.id == graphql_audit_user.id
    assert er_transition.laika_reviewed is True
    assert updated_evidence.is_laika_reviewed is False


@pytest.mark.functional(permissions=['fieldwork.add_evidence'])
def test_add_auditor_evidence_request(
    graphql_audit_client, audit, requirement, evidence
):
    evidence_count = Evidence.objects.count()
    response = graphql_audit_client.execute(
        ADD_AUDITOR_EVIDENCE_REQUEST,
        variables={
            'input': dict(
                auditId=str(audit.id),
                name='Test name',
                instructions='Test instructions',
                relatedRequirementsIds=[str(requirement.id)],
            )
        },
    )
    new_evidence = response['data']['addAuditorEvidenceRequest']

    assert new_evidence['evidence']['displayId'] == 'ER-2'
    assert Evidence.objects.count() == (evidence_count + 1)


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_auditor_new_evidence_request_display_id(
    graphql_audit_client, audit, evidence
):
    response = graphql_audit_client.execute(
        GET_NEW_AUDITOR_EVIDENCE_REQUEST_DISPLAY_ID,
        variables={
            'auditId': audit.id,
        },
    )

    new_evidence = response['data']['auditorNewEvidenceRequestDisplayId']
    assert new_evidence['displayId'] == 'ER-2'


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_auditor_evidence_request(
    graphql_audit_client, audit, requirement, evidence
):
    new_name = 'New name'
    new_instructions = 'New instructions'
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_REQUEST,
        variables={
            'input': dict(
                auditId=str(audit.id),
                evidenceId=str(evidence.id),
                name=new_name,
                instructions=new_instructions,
                relatedRequirementsIds=[str(requirement.id)],
            )
        },
    )
    updated_evidence = response['data']['updateAuditorEvidenceRequest']
    assert updated_evidence['evidence']['name'] == new_name
    assert updated_evidence['evidence']['instructions'] == new_instructions
    assert len(updated_evidence['evidence']['requirements']) == 1


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_auditor_evidence_request_open(
    graphql_audit_client, audit, requirement, evidence
):
    evidence.status = ER_ACCEPTED_STATUS
    evidence.save()

    new_name = 'New name'
    new_instructions = 'New instructions'
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_REQUEST,
        variables={
            'input': dict(
                auditId=str(audit.id),
                evidenceId=str(evidence.id),
                name=new_name,
                instructions=new_instructions,
                relatedRequirementsIds=[str(requirement.id)],
            )
        },
    )
    error_msg = response['errors'][0]['message']
    assert error_msg == 'Status of the evidence should be open for updating'


ER_SUBMITTED = 'Submitted'
ER_OPEN = 'Open'


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_attachments_status_from_open_to_submitted(
    graphql_audit_client, audit, evidence
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[evidence.id], status=ER_SUBMITTED, auditId=evidence.audit.id
            )
        },
    )

    evidence_updated = Evidence.objects.get(id=evidence.id, audit=audit)
    attachments = evidence_updated.attachments.all()

    assert evidence_updated.status == ER_STATUS_DICT[ER_SUBMITTED]

    for attachment in attachments:
        assert attachment.has_been_submitted is True


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_evidence_status_from_submitted_to_open(
    graphql_audit_client, audit, evidence
):
    evidence.status = ER_STATUS_DICT[ER_SUBMITTED]
    evidence.save()
    attachments = evidence.attachments.all()

    for attachment in attachments:
        attachment.has_been_submitted = True
        attachment.save()

    transition_reasons = 'Policy needs updating'
    extra_notes = 'bla nla'
    graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[evidence.id],
                status=ER_OPEN,
                auditId=evidence.audit.id,
                transitionReasons=transition_reasons,
                extraNotes=extra_notes,
            )
        },
    )

    evidence_updated = Evidence.objects.get(id=evidence.id, audit=audit)
    current_attachments = evidence_updated.attachments.all()

    assert evidence_updated.status == ER_STATUS_DICT[ER_OPEN]

    er_transition = evidence.status_transitions.first()
    assert er_transition.transition_reasons == transition_reasons
    assert er_transition.extra_notes == extra_notes

    for attachment in current_attachments:
        assert attachment.has_been_submitted is True


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_er_to_submitted_does_not_update_already_submitted_attachment(
    graphql_audit_client, evidence
):
    attachment = evidence.attachments.first()

    attachment.has_been_submitted = True
    attachment.save()
    attachment_old_updated_at = attachment.updated_at

    graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[evidence.id], status=ER_SUBMITTED, auditId=evidence.audit.id
            )
        },
    )

    current_attachment = Attachment.objects.get(
        id=attachment.id,
    )

    assert attachment_old_updated_at == current_attachment.updated_at


@pytest.mark.parametrize(
    'status', [ER_OPEN_STATUS, ER_SUBMITTED_STATUS, ER_ACCEPTED_STATUS]
)
@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_all_evidence_attachments(
    status,
    graphql_audit_client,
    graphql_audit_user,
    audit,
    evidence,
    evidence_attachment,
    evidence_with_attachments,
):
    evidence_with_attachments.status = status
    evidence_with_attachments.save()
    delete_attachments_input = {
        'input': {
            "auditId": audit.id,
            "evidenceIds": [evidence.id, evidence_with_attachments.id],
        }
    }

    response = graphql_audit_client.execute(
        DELETE_AUDITOR_ALL_EVIDENCE_ATTACHMENTS, variables=delete_attachments_input
    )

    evidence_response = response['data']['deleteAuditorAllEvidenceAttachments'][
        'evidence'
    ]
    assert len(evidence_response) == 2
    assert len(evidence_response[0]['attachments']) == 0
    assert len(evidence_response[1]['attachments']) == 0

    deleted_attachments = Attachment.objects.filter(
        evidence_id=evidence_with_attachments.id
    )
    for att in deleted_attachments:
        assert att.deleted_by.id == graphql_audit_user.id


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_auditor_evidence_request_instructions(
    graphql_audit_client, audit, requirement, evidence
):
    new_name = 'New name'
    new_instructions = '<p>New instructions</p>'
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_EVIDENCE_REQUEST,
        variables={
            'input': dict(
                auditId=str(audit.id),
                evidenceId=str(evidence.id),
                name=new_name,
                instructions=new_instructions,
                relatedRequirementsIds=[str(requirement.id)],
            )
        },
    )
    updated_evidence = response['data']['updateAuditorEvidenceRequest']
    assert updated_evidence['evidence']['name'] == new_name
    assert updated_evidence['evidence']['instructions'] == '<p>New instructions</p>'
    assert len(updated_evidence['evidence']['requirements']) == 1


@pytest.mark.functional(permissions=['fieldwork.add_evidence'])
def test_add_auditor_evidence_request_instructions(
    graphql_audit_client, audit, requirement, evidence
):
    evidence_count = Evidence.objects.count()
    response = graphql_audit_client.execute(
        ADD_AUDITOR_EVIDENCE_REQUEST,
        variables={
            'input': dict(
                auditId=str(audit.id),
                name='Test name',
                instructions='<p>Test instructions</p>',
                relatedRequirementsIds=[str(requirement.id)],
            )
        },
    )
    new_evidence = response['data']['addAuditorEvidenceRequest']

    assert new_evidence['evidence']['displayId'] == 'ER-2'
    assert new_evidence['evidence']['instructions'] == '<p>Test instructions</p>'
    assert Evidence.objects.count() == (evidence_count + 1)
