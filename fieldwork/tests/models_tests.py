import tempfile

import pytest
from django.core.files import File

from fieldwork.constants import LAIKA_EVIDENCE_SOURCE_TYPE
from fieldwork.models import Attachment, EVFetchLogicFilter
from policy.tests.factory import create_published_empty_policy

POLICY_NAME = 'Policy Test.pdf'
POLICY_RENAMED = 'Policy Renamed Test.pdf'
TRAINING_RENAMED = 'Training Renamed Test.pdf'
TEAM_RENAMED = 'Team Renamed Test.pdf'


@pytest.mark.functional
def test_fetch_runs_first_time_for_policy(
    graphql_organization, graphql_user, evidence_no_attachments
):
    policy = create_published_empty_policy(
        organization=graphql_organization, user=graphql_user, name=POLICY_NAME
    )

    evidence_no_attachments.add_attachment(
        file_name=policy.name,
        policy=policy,
        file=File(file=tempfile.TemporaryFile(), name=policy.name),
        is_from_fetch=True,
    )

    assert evidence_no_attachments.attachments.count() == 1


@pytest.mark.functional
def test_fetch_runs_second_time_for_policy(
    graphql_organization, graphql_user, evidence_no_attachments
):
    # Since the policy already exists, then policy is updated not duplicated
    policy = create_published_empty_policy(
        organization=graphql_organization, user=graphql_user, name=POLICY_NAME
    )

    evidence_no_attachments.add_attachment(
        file_name=policy.name,
        policy=policy,
        file=File(file=tempfile.TemporaryFile(), name=policy.name),
        is_from_fetch=True,
    )
    assert evidence_no_attachments.attachments.count() == 1
    evidence_no_attachments.add_attachment(
        file_name=policy.name,
        policy=policy,
        file=File(file=tempfile.TemporaryFile(), name=policy.name),
        is_from_fetch=True,
    )
    attachment = evidence_no_attachments.attachments.all()[0]
    assert evidence_no_attachments.attachments.count() == 1
    assert attachment.name == POLICY_NAME


@pytest.mark.functional
def test_fetch_runs_after_renaming_policy(
    graphql_organization, graphql_user, evidence_no_attachments
):
    policy = create_published_empty_policy(
        organization=graphql_organization, user=graphql_user, name=POLICY_NAME
    )

    evidence_no_attachments.add_attachment(
        file_name=policy.name,
        policy=policy,
        file=File(file=tempfile.TemporaryFile(), name=policy.name),
        is_from_fetch=True,
    )
    assert evidence_no_attachments.attachments.count() == 1

    attachment = evidence_no_attachments.attachments.all()[0]
    attachment.name = POLICY_RENAMED
    attachment.save()

    evidence_no_attachments.add_attachment(
        file_name=policy.name,
        policy=policy,
        file=File(file=tempfile.TemporaryFile(), name=policy.name),
        is_from_fetch=True,
    )

    attachment_renamed = evidence_no_attachments.attachments.all()[0]
    new_attachment = evidence_no_attachments.attachments.all()[1]
    assert evidence_no_attachments.attachments.count() == 2
    assert new_attachment.name == POLICY_NAME
    assert attachment_renamed.name == POLICY_RENAMED


@pytest.mark.functional
def test_fetch_runs_after_submitting_er_with_policy(
    graphql_organization, graphql_user, evidence_no_attachments
):
    policy = create_published_empty_policy(
        organization=graphql_organization, user=graphql_user, name=POLICY_NAME
    )

    evidence_no_attachments.add_attachment(
        file_name=policy.name,
        policy=policy,
        file=File(file=tempfile.TemporaryFile(), name=policy.name),
        is_from_fetch=True,
    )
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.all()[0]
    attachment.has_been_submitted = True
    attachment.save()

    evidence_no_attachments.add_attachment(
        file_name=policy.name,
        policy=policy,
        file=File(file=tempfile.TemporaryFile(), name=policy.name),
        is_from_fetch=True,
    )

    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_first_time_for_training(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    training,
    fetch_logic_training_log,
    tmp_attachment_training_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[training.name],
        fetch_logic=fetch_logic_training_log,
    )
    ev_fetch_logic.run_filter_query()
    attachments_qs = evidence_no_attachments.attachments
    assert attachments_qs.count() == 1
    assert attachments_qs.first().origin_source_object == training


@pytest.mark.functional
def test_fetch_runs_first_time_for_documents(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    fetch_logic_document,
    document,
    tmp_attachment_document_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[document.evidence.name],
        fetch_logic=fetch_logic_document,
    )
    ev_fetch_logic.run_filter_query()
    attachments_qs = evidence_no_attachments.attachments
    assert attachments_qs.count() == 1
    assert attachments_qs.first().origin_source_object == document.evidence


@pytest.mark.functional
def test_fetch_runs_first_time_for_policies(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    fetch_logic_policy,
    policy,
    tmp_attachment_policy_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[policy.name],
        fetch_logic=fetch_logic_policy,
    )
    ev_fetch_logic.run_filter_query()
    attachments_qs = evidence_no_attachments.attachments
    assert attachments_qs.count() == 1
    assert attachments_qs.first().origin_source_object == policy


@pytest.mark.functional
def test_fetch_runs_second_time_for_training(
    graphql_organization,
    graphql_user,
    training,
    evidence_no_attachments,
    fetch_logic_training_log,
    tmp_attachment_training_type,
):
    # Since the training already exists, then training is updated not
    # duplicated
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[training.name],
        fetch_logic=fetch_logic_training_log,
    )
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1


@pytest.mark.functional
def test_fetch_runs_after_renaming_training(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    training,
    fetch_logic_training_log,
    tmp_attachment_training_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[training.name],
        fetch_logic=fetch_logic_training_log,
    )
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.name = TRAINING_RENAMED
    attachment.save()

    ev_fetch_logic.run_filter_query()

    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_after_submitting_er_with_training(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    training,
    fetch_logic_training_log,
    tmp_attachment_training_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[training.name],
        fetch_logic=fetch_logic_training_log,
    )
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.has_been_submitted = True
    attachment.save()

    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_first_time_for_team(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    team,
    fetch_logic_team_log,
    tmp_attachment_team_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[team.name],
        fetch_logic=fetch_logic_team_log,
    )
    ev_fetch_logic.run_filter_query()
    attachment_qs = evidence_no_attachments.attachments
    assert attachment_qs.count() == 1
    assert attachment_qs.first().origin_source_object == team


@pytest.mark.functional
def test_fetch_runs_second_time_for_team(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    team,
    fetch_logic_team_log,
    tmp_attachment_team_type,
):
    # Since the team file already exists, then file is updated not duplicated
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[team.name],
        fetch_logic=fetch_logic_team_log,
    )
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1


@pytest.mark.functional
def test_fetch_runs_after_renaming_team(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    team,
    fetch_logic_team_log,
    tmp_attachment_team_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[team.name],
        fetch_logic=fetch_logic_team_log,
    )
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.name = TEAM_RENAMED
    attachment.save()

    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_after_submitting_er_with_team(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    team,
    fetch_logic_team_log,
    tmp_attachment_team_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[team.name],
        fetch_logic=fetch_logic_team_log,
    )
    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.has_been_submitted = True
    attachment.save()

    ev_fetch_logic.run_filter_query()
    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.django_db
def test_fetch_runs_for_team_store_source(
    graphql_organization,
    graphql_user,
    evidence_no_attachments,
    team,
    fetch_logic_team_log,
    tmp_attachment_team_type,
):
    ev_fetch_logic = EVFetchLogicFilter(
        organization=graphql_organization,
        evidence=evidence_no_attachments,
        results=[team.name],
        fetch_logic=fetch_logic_team_log,
    )
    ev_fetch_logic.run_filter_query()

    attachment = evidence_no_attachments.attachments.first()
    assert evidence_no_attachments.attachments.count() == 1
    assert attachment.source.name == LAIKA_EVIDENCE_SOURCE_TYPE


@pytest.mark.django_db
def test_er_attachment_duplicate_name_exception(evidence):
    attachment = Attachment.objects.get(
        name='attachment',
        evidence=evidence,
    )
    with pytest.raises(Exception) as excinfo:
        attach_input = dict(new_name='attachment', evidence_id=evidence.id)
        attachment.rename(attach_input)

        assert (
            str(excinfo.value) == 'This file name already exists. Use a different name.'
        )
