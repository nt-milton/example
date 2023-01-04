import pytest

from alert.tests.factory import create_evidence
from audit.constants import AUDIT_FIRMS
from audit.tests.factory import create_audit, create_audit_firm
from comment.launchpad import (
    ControlCommentMapper,
    ControlMentionCommentMapper,
    ControlReplyCommentMapper,
    EvidenceRequestCommentMapper,
    EvidenceRequestMentionCommentMapper,
    EvidenceRequestReplyCommentMapper,
)
from comment.models import Comment, Mention, Reply
from control.models import ControlComment
from control.tests import create_control
from fieldwork.models import EvidenceComment
from user.tests import create_user


@pytest.fixture
def audit(graphql_organization):
    return create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=create_audit_firm(AUDIT_FIRMS[0]),
    )


@pytest.fixture
def evidence(audit):
    return create_evidence(audit, display_id='ev-1', name='Ev1', status='open')


@pytest.fixture
def evidence_comment(graphql_user, evidence):
    comment = Comment.objects.create(owner=graphql_user, content='Comment content')
    return EvidenceComment.objects.create(evidence=evidence, comment=comment)


@pytest.fixture
def control(graphql_organization):
    return create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control test',
        description='Test Description',
    )


@pytest.fixture
def control_comment(graphql_user, control):
    comment = Comment.objects.create(owner=graphql_user, content='Comment content')
    return ControlComment.objects.create(control=control, comment=comment)


@pytest.mark.functional
def test_control_comments(graphql_user, graphql_organization, control, control_comment):
    john = create_user(
        graphql_organization,
        email='john@heylaika.com',
        first_name='John',
        last_name='John',
    )

    kevin = create_user(
        graphql_organization,
        email='kevin@heylaika.com',
        first_name='Kevin',
        last_name='Kevin',
    )

    comment = control_comment.comment
    reply = Reply.objects.create(
        owner=graphql_user, parent=comment, content='Reply test'
    )

    mention_one = Mention.objects.create(user=john, reply=reply)
    mention_two = Mention.objects.create(user=kevin, comment=comment)

    control_mention_mapper = ControlMentionCommentMapper(graphql_organization.id)
    control_mentions = control_mention_mapper.get_comments()

    assert len(control_mentions) == 2
    assert control_mentions[0].__dict__ == dict(
        id=f'cm-{mention_one.id}',
        description=reply.content,
        name=control.name,
        url=f'/controls/{control.id}?activeTab=Comments',
        mention='@John John',
    )

    assert control_mentions[1].__dict__ == dict(
        id=f'cm-{mention_two.id}',
        description=comment.content,
        name=control.name,
        url=f'/controls/{control.id}?activeTab=Comments',
        mention='@Kevin Kevin',
    )

    control_comment_mapper = ControlCommentMapper(graphql_organization.id)
    control_comments = control_comment_mapper.get_comments()

    assert len(control_comments) == 1
    assert control_comments[0].__dict__ == dict(
        id=f'cc-{control_comment.id}',
        name=control.name,
        owner=comment.owner_name,
        description=comment.content,
        url=f'/controls/{control.id}?activeTab=Comments',
    )

    control_reply_mapper = ControlReplyCommentMapper(graphql_organization.id)
    control_replies = control_reply_mapper.get_comments()

    assert len(control_replies) == 1
    assert control_replies[0].__dict__ == dict(
        id=f'cr-{reply.id}',
        name=control.name,
        owner=reply.owner_name,
        description=reply.content,
        url=f'/controls/{control.id}?activeTab=Comments',
    )


@pytest.mark.functional
def test_evidence_request_comments(
    graphql_user, graphql_organization, audit, evidence, evidence_comment
):
    noah = create_user(
        graphql_organization,
        email='noah@heylaika.com',
        first_name='Noah',
        last_name='Noah',
    )

    smith = create_user(
        graphql_organization,
        email='smith@heylaika.com',
        first_name='Smith',
        last_name='Smith',
    )

    accepted_evidence = create_evidence(
        audit, display_id='ev-accepted-1', name='Eva1', status='auditor_accepted'
    )
    excluded_comment = Comment.objects.create(
        owner=graphql_user, content='Auditor accepted comment'
    )
    EvidenceComment.objects.create(evidence=accepted_evidence, comment=excluded_comment)
    excluded_reply = Reply.objects.create(
        owner=graphql_user, parent=excluded_comment, content='Reply accepted test'
    )
    Mention.objects.create(user=noah, reply=excluded_reply)

    comment = evidence_comment.comment
    reply = Reply.objects.create(
        owner=graphql_user, parent=comment, content='Reply test'
    )

    mention_one = Mention.objects.create(user=noah, reply=reply)
    mention_two = Mention.objects.create(user=smith, comment=comment)

    evidence_mention_mapper = EvidenceRequestMentionCommentMapper(
        graphql_organization.id
    )
    evidence_mentions = evidence_mention_mapper.get_comments()

    assert len(evidence_mentions) == 2
    assert evidence_mentions[0].__dict__ == dict(
        id=f'erm-{mention_one.id}',
        description=reply.content,
        name=evidence.name,
        url=f'/audits/{audit.id}/evidence-detail/{evidence.id}?activeTab=Comments',
        mention='@Noah Noah',
    )

    assert evidence_mentions[1].__dict__ == dict(
        id=f'erm-{mention_two.id}',
        description=comment.content,
        name=evidence.name,
        url=f'/audits/{audit.id}/evidence-detail/{evidence.id}?activeTab=Comments',
        mention='@Smith Smith',
    )

    evidence_comment_mapper = EvidenceRequestCommentMapper(graphql_organization.id)
    evidence_comments = evidence_comment_mapper.get_comments()

    assert len(evidence_comments) == 1
    assert evidence_comments[0].__dict__ == dict(
        id=f'erc-{evidence_comment.id}',
        name=evidence.name,
        owner=comment.owner_name,
        description=comment.content,
        url=f'/audits/{audit.id}/evidence-detail/{evidence.id}?activeTab=Comments',
    )

    evidence_reply_mapper = EvidenceRequestReplyCommentMapper(graphql_organization.id)
    evidence_replies = evidence_reply_mapper.get_comments()

    assert len(evidence_replies) == 1
    assert evidence_replies[0].__dict__ == dict(
        id=f'err-{reply.id}',
        name=evidence.name,
        owner=reply.owner_name,
        description=reply.content,
        url=f'/audits/{audit.id}/evidence-detail/{evidence.id}?activeTab=Comments',
    )
