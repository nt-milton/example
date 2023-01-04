from unittest.mock import patch

import pytest

from action_item.models import ActionItemTags
from drive.evidence_handler import create_laika_paper_evidence
from fieldwork.constants import ADD_ATTACHMENT_INVALID_MONITOR_MESSAGE, ER_STATUS_DICT
from fieldwork.models import Attachment, Evidence
from user.constants import ROLE_SUPER_ADMIN

from .mutations import (
    ADD_EVIDENCE_ATTACHMENT,
    ASSIGN_EVIDENCE,
    DELETE_AUDITEE_ALL_EVIDENCE_ATTACHMENTS,
    DELETE_EVIDENCE_ATTACHMENT,
    RUN_FETCH_EVIDENCE,
    UPDATE_EVIDENCE,
    UPDATE_EVIDENCE_LAIKA_REVIEWED,
    UPDATE_EVIDENCE_STATUS,
)
from .queries import (
    GET_ALL_EVIDENCE,
    GET_AUDITEE_ACCEPTED_EVIDENCE_COUNT,
    GET_AUDITEE_DOCUMENTS,
    GET_AUDITEE_EVIDENCE,
    GET_AUDITEE_EVIDENCE_ASSIGNEES,
    GET_AUDITEE_REVIEWED_EVIDENCE_COUNT,
    GET_FIELDWORK_AUDITEE_EVIDENCE,
)
from .test_utils import create_evidence_attachment

ER_OPEN_STATUS = 'open'
ER_ACCEPTED_STATUS = 'auditor_accepted'
DELETE_ATTCH_ERROR_MSG = 'Delete cannot be applied after ERs are Laika Reviewed'


@pytest.fixture
def evidence_reviewed_submitted(graphql_organization, audit):
    evidence = Evidence.objects.create(
        audit=audit,
        display_id='4',
        name='Ev4',
        status='submitted',
        is_laika_reviewed=True,
    )
    create_evidence_attachment(graphql_organization, evidence)

    return evidence


@pytest.fixture
def action_items_tags(graphql_organization):
    tags = 'BC/DR Plan, Network Diagram'

    ActionItemTags.objects.create(item_text='action item test', tags=tags)


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
@patch(
    'auditee.schema.get_evidence_by_args',
    return_value=Evidence.objects.all(),
)
def test_get_all_evidence(get_evidence_by_args_mock, graphql_client, evidence):
    response = graphql_client.execute(
        GET_ALL_EVIDENCE, variables={'auditId': '1', 'status': 'Open'}
    )

    get_evidence_by_args_mock.assert_called_once()
    assert len(response['data']['auditeeAllEvidence']['evidence']) == 1
    assert (
        response['data']['auditeeAllEvidence']['__typename']
        == 'FieldworkEvidenceAllResponseType'
    )


@pytest.mark.functional(permissions=['fieldwork.review_evidence'])
def test_update_evidence_laika_reviewed(graphql_client, graphql_user, evidence):
    assign_evidence_input = {
        'input': dict(evidenceIds=[str(evidence.id)], auditId=evidence.audit.id)
    }

    response = graphql_client.execute(
        UPDATE_EVIDENCE_LAIKA_REVIEWED, variables=assign_evidence_input
    )

    assert response['data']['updateAuditeeEvidenceLaikaReviewed'] is not None


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_auditee_accepted_evidence_count(
    graphql_client, audit, evidence, evidence_with_attachments
):
    evidence.status = ER_ACCEPTED_STATUS
    evidence.save()
    response = graphql_client.execute(
        GET_AUDITEE_ACCEPTED_EVIDENCE_COUNT, variables={'auditId': audit.id}
    )
    results = response["data"]["auditeeAcceptedEvidenceCount"]
    assert results['acceptedEvidence'] == 1
    assert results['totalEvidence'] == 2


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_auditee_reviewed_evidence_count(
    graphql_client, audit, evidence, evidence_with_attachments
):
    evidence.is_laika_reviewed = True
    evidence.save()
    response = graphql_client.execute(
        GET_AUDITEE_REVIEWED_EVIDENCE_COUNT, variables={'auditId': audit.id}
    )
    results = response['data']['auditeeReviewedEvidenceCount']
    assert results['laikaReviewedEvidence'] == 1
    assert results['totalEvidence'] == 2


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_auditee_evidence(
    graphql_client,
    audit,
    evidence,
):
    response = graphql_client.execute(
        GET_AUDITEE_EVIDENCE,
        variables={'evidenceId': str(evidence.id), 'auditId': audit.id},
    )
    evidence = response['data']['auditeeEvidence']
    assert evidence['name'] == 'Ev1'


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_auditee_assignees_for_evidence(
    graphql_client,
    laika_admin_user,
    audit,
):
    get_assignees_input = {'auditId': str(audit.id)}

    response = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_ASSIGNEES, variables=get_assignees_input
    )

    users = response["data"]["auditeeAssigneesForEvidence"]
    assert users[0]['email'] == 'laika_admin_user@heylaika.com'


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_customer_documents(graphql_client, audit):
    organization, user = graphql_client.context.values()
    create_laika_paper_evidence(organization, user)
    response = graphql_client.execute(
        GET_AUDITEE_DOCUMENTS, variables={'auditId': audit.id}
    )
    response_data = response['data']['auditeeDocuments']
    documents = response_data['documents']

    assert response_data is not None
    assert len(documents) == 1


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_fieldwork_auditee_evidence(graphql_client, evidence):
    response = graphql_client.execute(
        GET_FIELDWORK_AUDITEE_EVIDENCE, variables={'auditId': '1', 'status': 'Open'}
    )
    assert len(response['data']['auditeeEvidenceList']) == 1


@pytest.mark.functional(permissions=['fieldwork.assign_evidence'])
def test_assign_auditee_evidence(graphql_client, laika_admin_user, evidence):
    laika_admin_user.role = 'SuperAdmin'
    laika_admin_user.save()
    assign_evidence_input = {
        'input': dict(
            evidenceIds=[str(evidence.id)],
            email=laika_admin_user.email,
            auditId=evidence.audit.id,
        )
    }

    response = graphql_client.execute(ASSIGN_EVIDENCE, variables=assign_evidence_input)

    result = response['data']['assignAuditeeEvidence']

    assert result['ids'][0] == str(evidence.id)


@pytest.mark.functional(permissions=['fieldwork.fetch_evidence_attachment'])
def test_run_fetch_for_all_evidence(
    graphql_client,
    graphql_user,
    graphql_organization,
    audit,
):
    run_fetch_evidence_input = {
        'input': dict(
            auditId=str(audit.id),
            evidenceIds=[],
        )
    }

    response = graphql_client.execute(
        RUN_FETCH_EVIDENCE, variables=run_fetch_evidence_input
    )

    assert response['data']['runFetchEvidence']['auditId'] == str(audit.id)


@pytest.mark.functional(permissions=['fieldwork.fetch_evidence_attachment'])
@pytest.mark.skipif(
    True,
    reason="Do not run this test because the mutation uses regex expresion for sorting",
)
def test_run_fetch_for_evidence_ids(
    graphql_client,
    graphql_user,
    graphql_organization,
    audit,
    evidence,
    evidence_attachment,
    fetch_logic_document,
    action_item,
    action_item_evidence,
    action_items_tags,
):
    evidence.fetch_logic.add(fetch_logic_document)
    evidence.attachment.add(evidence_attachment)
    evidence.save()

    run_fetch_evidence_input = {
        'input': dict(
            auditId=str(audit.id),
            evidenceIds=[evidence.id],
        )
    }
    response = graphql_client.execute(
        RUN_FETCH_EVIDENCE, variables=run_fetch_evidence_input
    )
    evidence_updated = Evidence.objects.get(id=evidence.id)
    attachments = evidence_updated.attachments

    assert response['data']['runFetchEvidence']['auditId'] == str(audit.id)
    assert evidence_updated.is_fetch_logic_accurate is True
    assert evidence_updated.description == 'This is the fetch doc description'
    assert attachments.count() == 2
    assert attachments.filter(name=action_item_evidence.name).exists() is True


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_evidence_status(graphql_client, graphql_user, evidence):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()
    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
        variables={
            'input': dict(ids=['1'], status='Submitted', auditId=evidence.audit.id)
        },
    )
    updated_evidence = Evidence.objects.get(display_id=evidence.display_id)
    transition = updated_evidence.status_transitions.first()
    assert updated_evidence.status == ER_SUBMITTED_STATUS
    assert transition.transitioned_by.id == graphql_user.id
    assert transition.laika_reviewed is False
    assert updated_evidence.is_laika_reviewed is True


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_evidence_status_back_to_open(
    graphql_client, evidence_reviewed_submitted
):
    evidence_reviewed_submitted.times_moved_back_to_open = 3
    evidence_reviewed_submitted.save()
    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[str(evidence_reviewed_submitted.id)],
                status='Open',
                auditId=evidence_reviewed_submitted.audit.id,
            )
        },
    )

    er = Evidence.objects.get(display_id=evidence_reviewed_submitted.display_id)

    er_transition = er.status_transitions.first()
    # When transition from auditee side we won't store these values
    assert er_transition.transition_reasons == ''
    assert er_transition.extra_notes is None

    assert not er.is_laika_reviewed
    assert er.times_moved_back_to_open == 1


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachment_laikapaper(
    graphql_client,
    graphql_user,
    graphql_organization,
    evidence,
    document,
    officer,
    team,
    vendor,
    training,
):
    assign_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            documents=[document.evidence.id],
            policies=[],
            timeZone='UTC',
            officers=[officer.id],
            teams=[team.id],
            objectsIds=[],
            vendors=[vendor.id],
            trainings=[training.id],
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=assign_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    for attachment in updated_evidence.attachments:
        assert not attachment.file.name.endswith('.laikapaper')


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachment_origin_source(
    graphql_client,
    graphql_user,
    graphql_organization,
    evidence,
    document,
    team,
    training,
):
    assign_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            documents=[document.evidence.id],
            policies=[],
            timeZone='UTC',
            teams=[team.id],
            objectsIds=[],
            trainings=[training.id],
        )
    }
    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=assign_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    # Need to filter cause by default there was one attachment already created in the ER
    filtered_attachments = [
        attach
        for attach in updated_evidence.attachments
        if attach.origin_source_object is not None
    ]
    for attachment in filtered_attachments:
        assert attachment.origin_source_object in [team, document.evidence, training]


@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_evidence_attachment(
    graphql_client,
    graphql_user,
    graphql_organization,
    audit,
    evidence,
    evidence_attachment,
):
    delete_attachment_input = {
        'input': dict(
            attachmentId=str(evidence_attachment.id),
            evidenceId=str(evidence.id),
            auditId=str(audit.id),
        )
    }

    response = graphql_client.execute(
        DELETE_EVIDENCE_ATTACHMENT, variables=delete_attachment_input
    )
    assert response['data']['deleteAuditeeEvidenceAttachment']['attachmentId'] == str(
        evidence_attachment.id
    )
    updated_attach = Attachment.objects.get(id=evidence_attachment.id)
    assert updated_attach.deleted_by.id == graphql_user.id


@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_evidence_attachment_that_has_been_submitted(
    graphql_client, audit, evidence, evidence_attachment
):
    evidence_attachment.has_been_submitted = True
    evidence_attachment.save()
    delete_attachment_input = {
        'input': dict(
            attachmentId=str(evidence_attachment.id),
            evidenceId=str(evidence.id),
            auditId=str(audit.id),
        )
    }

    response = graphql_client.execute(
        DELETE_EVIDENCE_ATTACHMENT, variables=delete_attachment_input
    )

    assert len(response['errors']) == 1


@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_laika_reviewed_evidence_attachment(
    graphql_client, audit, evidence, evidence_attachment
):
    evidence.is_laika_reviewed = True
    evidence.save()
    delete_attachment_input = {
        'input': dict(
            attachmentId=str(evidence_attachment.id),
            evidenceId=str(evidence.id),
            auditId=str(audit.id),
        )
    }

    response = graphql_client.execute(
        DELETE_EVIDENCE_ATTACHMENT, variables=delete_attachment_input
    )

    assert response['errors'][0].get('message') == DELETE_ATTCH_ERROR_MSG


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_evidence(graphql_client, evidence):
    description = 'This is description for ER1'
    graphql_client.execute(
        UPDATE_EVIDENCE,
        variables={
            'input': dict(evidenceId=evidence.id, read=True, description=description)
        },
    )
    updated_evidence = Evidence.objects.get(id=evidence.id)
    assert updated_evidence.read is not False
    assert updated_evidence.description != evidence.description
    assert updated_evidence.description == description


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_metrics_of_times_moved_to_open(graphql_client, evidence_reviewed_submitted):
    evidence_reviewed_submitted.times_moved_back_to_open = 3
    evidence_reviewed_submitted.save()
    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[str(evidence_reviewed_submitted.id)],
                status='Open',
                auditId=evidence_reviewed_submitted.audit.id,
            )
        },
    )

    evidence = Evidence.objects.get(display_id=evidence_reviewed_submitted.display_id)

    assert evidence_reviewed_submitted.times_moved_back_to_open == 3
    assert evidence.times_moved_back_to_open == 1


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_store_evidence_status_transitions_with_same_status(graphql_client, evidence):
    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
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
    graphql_client, evidence
):
    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
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
def test_store_auditee_evidence_status_transition(
    graphql_client, graphql_user, audit, evidence
):
    graphql_client.execute(
        UPDATE_EVIDENCE,
        variables={
            'input': dict(
                auditId=str(audit.id), evidenceId=str(evidence.id), status='Submitted'
            )
        },
    )

    updated_evidence = Evidence.objects.get(id=evidence.id)
    evidence_transitions = updated_evidence.status_transitions.all()
    transition = evidence_transitions[0]
    assert evidence_transitions.count() == 1
    assert transition.from_status == ER_OPEN_STATUS
    assert transition.to_status == ER_SUBMITTED_STATUS
    assert transition.created_at is not None
    assert transition.transitioned_by.id == graphql_user.id
    assert transition.laika_reviewed is False


ER_SUBMITTED = 'Submitted'
ER_OPEN = 'Open'


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_attachments_status_from_open_to_submitted(
    graphql_client, audit, evidence_with_attachments
):
    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[evidence_with_attachments.id],
                status=ER_SUBMITTED,
                auditId=evidence_with_attachments.audit.id,
            )
        },
    )

    evidence_updated = Evidence.objects.get(
        id=evidence_with_attachments.id, audit=audit
    )
    attachments = evidence_updated.attachments.all()

    assert evidence_updated.status == ER_STATUS_DICT[ER_SUBMITTED]

    for attachment in attachments:
        assert attachment.has_been_submitted is True


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_evidence_status_from_submitted_to_open(
    graphql_client, audit, evidence_with_attachments
):
    evidence_with_attachments.status = ER_STATUS_DICT[ER_SUBMITTED]
    evidence_with_attachments.save()
    attachments = evidence_with_attachments.attachments.all()

    for attachment in attachments:
        attachment.has_been_submitted = True
        attachment.save()

    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[evidence_with_attachments.id],
                status=ER_OPEN,
                auditId=evidence_with_attachments.audit.id,
            )
        },
    )

    evidence_updated = Evidence.objects.get(
        id=evidence_with_attachments.id, audit=audit
    )
    current_attachments = evidence_updated.attachments.all()

    assert evidence_updated.status == ER_STATUS_DICT[ER_OPEN]

    for attachment in current_attachments:
        assert attachment.has_been_submitted is True


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_update_er_to_submitted_does_not_update_already_submitted_attachment(
    graphql_client, evidence_with_attachments
):
    attachment = evidence_with_attachments.attachments.first()

    attachment.has_been_submitted = True
    attachment.save()
    attachment_old_updated_at = attachment.updated_at

    graphql_client.execute(
        UPDATE_EVIDENCE_STATUS,
        variables={
            'input': dict(
                ids=[evidence_with_attachments.id],
                status=ER_SUBMITTED,
                auditId=evidence_with_attachments.audit.id,
            )
        },
    )

    current_attachment = Attachment.objects.get(
        id=attachment.id,
    )

    assert attachment_old_updated_at == current_attachment.updated_at


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachment_invalid_monitor(
    graphql_client,
    graphql_user,
    evidence,
    organization_monitor_flagged,
    monitor_result_flagged,
):
    add_attachment_input = {
        'input': dict(
            id=str(evidence.id),
            timeZone='UTC',
            monitors=[
                {
                    'id': str(organization_monitor_flagged.id),
                    'name': organization_monitor_flagged.name,
                }
            ],
        )
    }

    response = graphql_client.execute(
        ADD_EVIDENCE_ATTACHMENT, variables=add_attachment_input
    )
    result = response['data']['addAuditeeEvidenceAttachment']
    ids = result['documentIds']
    error = result['monitorsError']
    assert len(ids) == 0
    assert error['message'] == ADD_ATTACHMENT_INVALID_MONITOR_MESSAGE


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachment_with_valid_monitor(
    graphql_client,
    graphql_user,
    evidence,
    organization_monitor,
    monitor_result1,
    organization_monitor_flagged,
    monitor_result_flagged,
):
    add_attachment_input = {
        'input': dict(
            id=str(evidence.id),
            timeZone='UTC',
            monitors=[
                {'id': str(organization_monitor.id), 'name': organization_monitor.name},
                {
                    'id': str(organization_monitor_flagged.id),
                    'name': organization_monitor_flagged.name,
                },
            ],
        )
    }

    response = graphql_client.execute(
        ADD_EVIDENCE_ATTACHMENT, variables=add_attachment_input
    )
    result = response['data']['addAuditeeEvidenceAttachment']
    ids = result['documentIds']
    error = result['monitorsError']

    attach_match = [
        attach for attach in evidence.attachments.all() if 'Monitor Test' in attach.name
    ]

    assert len(attach_match) == 1
    assert len(ids) == 1
    assert error['message'] == ADD_ATTACHMENT_INVALID_MONITOR_MESSAGE
    assert attach_match[0].origin_source_object == organization_monitor.monitor


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_mark_as_laika_reviewed_when_super_admin_submit_er(
    graphql_client, graphql_user, audit, evidence
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()
    graphql_client.execute(
        UPDATE_EVIDENCE,
        variables={
            'input': dict(
                auditId=str(audit.id), evidenceId=str(evidence.id), status=ER_SUBMITTED
            )
        },
    )

    evidence = Evidence.objects.get(id=evidence.id)

    assert evidence.status == ER_SUBMITTED_STATUS
    assert evidence.is_laika_reviewed


@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_all_evidence_attachments(
    graphql_client, audit, evidence, evidence_attachment, evidence_with_attachments
):
    delete_attachments_input = {
        'input': {
            "auditId": audit.id,
            "evidenceIds": [evidence.id, evidence_with_attachments.id],
        }
    }

    response = graphql_client.execute(
        DELETE_AUDITEE_ALL_EVIDENCE_ATTACHMENTS, variables=delete_attachments_input
    )

    evidence_response = response['data']['deleteAuditeeAllEvidenceAttachments'][
        'evidence'
    ]
    assert len(evidence_response) == 2
    assert len(evidence_response[0]['attachments']) == 0
    assert len(evidence_response[1]['attachments']) == 0


@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_all_evidence_attachment_open_status_only(
    graphql_client,
    graphql_user,
    audit,
    evidence_reviewed_submitted,
    evidence_with_attachments,
):
    evidence_reviewed_submitted.is_laika_reviewed = False
    evidence_reviewed_submitted.save()
    delete_attachments_input = {
        'input': {
            "auditId": audit.id,
            "evidenceIds": [
                evidence_reviewed_submitted.id,
                evidence_with_attachments.id,
            ],
        }
    }

    graphql_client.execute(
        DELETE_AUDITEE_ALL_EVIDENCE_ATTACHMENTS, variables=delete_attachments_input
    )

    assert evidence_reviewed_submitted.attachments.count() > 0
    assert evidence_with_attachments.attachments.count() == 0

    deleted_attachments = Attachment.objects.filter(
        evidence_id=evidence_with_attachments.id
    )
    for att in deleted_attachments:
        assert att.deleted_by.id == graphql_user.id


@pytest.mark.functional(permissions=['fieldwork.delete_evidence_attachment'])
def test_delete_laika_reviewed_evidence_attachments(
    graphql_client, audit, evidence, evidence_attachment, evidence_with_attachments
):
    evidence.is_laika_reviewed = True
    evidence.save()
    delete_attachments_input = {
        'input': {
            "auditId": audit.id,
            "evidenceIds": [evidence.id, evidence_with_attachments.id],
        }
    }

    response = graphql_client.execute(
        DELETE_AUDITEE_ALL_EVIDENCE_ATTACHMENTS, variables=delete_attachments_input
    )

    assert response['errors'][0].get('message') == DELETE_ATTCH_ERROR_MSG


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_try_add_accepted_evidence_attachment(
    graphql_client,
    graphql_user,
    evidence,
    organization_monitor_flagged,
    monitor_result_flagged,
):
    evidence.status = ER_ACCEPTED_STATUS
    evidence.save()
    add_attachment_input = {
        'input': dict(
            id=str(evidence.id),
            timeZone='UTC',
            monitors=[
                {
                    'id': str(organization_monitor_flagged.id),
                    'name': organization_monitor_flagged.name,
                }
            ],
        )
    }

    response = graphql_client.execute(
        ADD_EVIDENCE_ATTACHMENT, variables=add_attachment_input
    )
    error_msg = response['errors'][0]['message']
    assert error_msg == 'Evidence request should be open'
