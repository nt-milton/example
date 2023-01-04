import pytest

from auditor.tests.mutations import (
    ADD_AUDITOR_COMMENT,
    ADD_AUDITOR_REPLY,
    DELETE_AUDITOR_COMMENT,
    DELETE_AUDITOR_REPLY,
    UPDATE_AUDITOR_COMMENT,
    UPDATE_AUDITOR_REPLY,
)
from comment.models import Reply
from fieldwork.models import RequirementComment

COMMENT_CONTENT = 'Test comment'
COMMENT_CONTENT_UPDATED = 'Test comment updated'


@pytest.fixture
def requirement_comment(graphql_audit_user, requirement):
    return RequirementComment.objects.custom_create(
        content=COMMENT_CONTENT,
        owner=graphql_audit_user,
        requirement_id=requirement.id,
        tagged_users=[],
    )


@pytest.fixture
def requirement_reply(graphql_audit_user, requirement_comment):
    reply = Reply.objects.create(
        owner=graphql_audit_user, content=COMMENT_CONTENT, parent=requirement_comment
    )
    requirement_comment.replies.add(reply)
    return reply


@pytest.mark.parametrize(
    'object_type, object_fixture, model',
    [
        ('requirement', 'requirement', RequirementComment),
    ],
)
@pytest.mark.functional(permissions=['comment.add_comment'])
def test_add_auditor_comment(
    object_type,
    object_fixture,
    model,
    graphql_audit_client,
    graphql_audit_user,
    request,
):
    add_comment_input = {
        'input': {
            'content': COMMENT_CONTENT,
            'objectId': request.getfixturevalue(object_fixture).id,
            'objectType': object_type,
            'taggedUsers': [],
        }
    }

    graphql_audit_client.execute(ADD_AUDITOR_COMMENT, variables=add_comment_input)

    assert model.objects.count() == 1


@pytest.mark.parametrize(
    'object_type, object_fixture, comment_fixture, model',
    [
        ('requirement', 'requirement', 'requirement_comment', RequirementComment),
    ],
)
@pytest.mark.functional(permissions=['comment.change_comment'])
def test_update_comment(
    object_type,
    object_fixture,
    comment_fixture,
    model,
    graphql_audit_client,
    graphql_audit_user,
    request,
):
    comment = request.getfixturevalue(comment_fixture)
    update_comment_input = {
        'input': {
            'content': COMMENT_CONTENT_UPDATED,
            'objectId': request.getfixturevalue(object_fixture).id,
            'objectType': object_type,
            'taggedUsers': [],
            'commentId': comment.id,
        }
    }

    graphql_audit_client.execute(UPDATE_AUDITOR_COMMENT, variables=update_comment_input)
    assert RequirementComment.objects.first().comment.content == COMMENT_CONTENT_UPDATED


@pytest.mark.parametrize(
    'object_type, object_fixture, comment_fixture',
    [
        ('requirement', 'requirement', 'requirement_comment'),
    ],
)
@pytest.mark.functional(permissions=['comment.add_reply'])
def test_add_requirement_comment_reply(
    object_type,
    object_fixture,
    comment_fixture,
    graphql_audit_client,
    graphql_audit_user,
    request,
):
    comment = request.getfixturevalue(comment_fixture)

    add_reply_input = {
        'input': {
            'content': COMMENT_CONTENT,
            'objectId': request.getfixturevalue(object_fixture).id,
            'objectType': object_type,
            'taggedUsers': [],
            'commentId': comment.id,
        }
    }

    graphql_audit_client.execute(ADD_AUDITOR_REPLY, variables=add_reply_input)
    assert Reply.objects.count() == 1


@pytest.mark.parametrize(
    'reply_fixture',
    [
        'requirement_reply',
    ],
)
@pytest.mark.functional(
    permissions=['comment.change_reply', 'fieldwork.change_requirementcomment']
)
def test_update_requirement_comment_reply(
    reply_fixture, graphql_audit_client, graphql_audit_user, requirement, request
):
    reply = request.getfixturevalue(reply_fixture)
    update_reply_input = {
        'input': {
            'content': COMMENT_CONTENT_UPDATED,
            'replyId': reply.id,
            'taggedUsers': [],
        }
    }

    graphql_audit_client.execute(UPDATE_AUDITOR_REPLY, variables=update_reply_input)
    assert Reply.objects.first().content == COMMENT_CONTENT_UPDATED


@pytest.mark.parametrize(
    'object_type, object_fixture, comment_fixture, comment_model',
    [
        ('requirement', 'requirement', 'requirement_comment', RequirementComment),
    ],
)
@pytest.mark.functional(
    permissions=['comment.delete_comment', 'fieldwork.delete_requirementcomment']
)
def test_delete_requirement_comment(
    object_type,
    object_fixture,
    comment_fixture,
    comment_model,
    graphql_audit_user,
    graphql_audit_client,
    requirement_comment,
    request,
):
    comment = request.getfixturevalue(comment_fixture)

    delete_comment_input = {
        'input': {
            'commentId': comment.id,
            'objectId': request.getfixturevalue(object_fixture).id,
            'objectType': object_type,
        }
    }

    graphql_audit_client.execute(DELETE_AUDITOR_COMMENT, variables=delete_comment_input)
    assert comment_model.objects.filter(comment__is_deleted=True).count() == 1


@pytest.mark.parametrize(
    'reply_fixture, comment_fixture',
    [
        ('requirement_reply', 'requirement_comment'),
    ],
)
@pytest.mark.functional(
    permissions=['comment.delete_reply', 'fieldwork.delete_requirementcomment']
)
def test_delete_requirement_reply(
    reply_fixture,
    comment_fixture,
    graphql_audit_client,
    graphql_audit_user,
    request,
):
    comment = request.getfixturevalue(comment_fixture)
    reply = request.getfixturevalue(reply_fixture)

    delete_reply_input = {
        'input': {
            'commentId': comment.id,
            'replyId': reply.id,
        }
    }

    graphql_audit_client.execute(DELETE_AUDITOR_REPLY, variables=delete_reply_input)
    assert Reply.objects.filter(is_deleted=True).count() == 1
