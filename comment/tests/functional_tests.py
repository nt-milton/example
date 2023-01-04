from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from alert.constants import ALERT_EMAIL_TEMPLATES, ALERT_TYPES
from audit.models import DraftReportComment
from audit.tests.factory import create_audit
from comment.constants import RESOLVED, UNRESOLVED
from comment.helpers import get_comment_by_id, get_reply_by_id
from comment.models import Comment, Mention, Reply
from comment.tests.mutations import (
    ADD_COMMENT,
    ADD_COMMENT_OR_REPLY,
    ADD_REPLY,
    DELETE_REPLY,
    UPDATE_REPLY,
)
from comment.utils import create_policy_mention_alerts, notify_add_policy_reply
from comment.validators import CONTROL, comment_type
from control.models import Control, ControlComment
from control.tests import create_control
from policy.models import Policy, PolicyComment
from user.constants import ALERT_PREFERENCES
from user.tests import create_user

CURRENT_TIME = datetime(2020, 3, 5, tzinfo=timezone.utc)


@pytest.fixture
def comment(graphql_user):
    return Comment.objects.create(owner=graphql_user, content='test comment')


@pytest.fixture
def user(graphql_organization):
    return create_user(graphql_organization, [], 'miguel+test@heylaika.com')


@pytest.fixture
def audit(graphql_organization, audit_firm):
    return create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=audit_firm,
    )


@pytest.fixture
def draft_report_comment(graphql_user, audit):
    comment = Comment.objects.create(owner=graphql_user, content='Comment content')
    DraftReportComment.objects.create(audit=audit, comment=comment, page=2)
    return comment


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
    ControlComment.objects.create(control=control, comment=comment)
    return comment


@pytest.fixture
def reply(graphql_user, comment):
    return Reply.objects.create(
        owner=graphql_user, content='test comment', parent=comment
    )


@pytest.mark.functional()
def test_get_comment_by_id(comment):
    assert not get_comment_by_id(None)
    assert get_comment_by_id(comment.id) == comment


@pytest.mark.functional()
def test_get_reply_by_id(reply):
    assert not get_reply_by_id(None)
    assert get_reply_by_id(reply.id) == reply


@pytest.mark.functional()
def test_comment_type_policy(graphql_user, graphql_organization, admin_user):
    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(owner=admin_user, content='This is a test comment')

    PolicyComment.objects.create(comment=comment, policy=policy)

    result = comment_type(comment)

    assert result == 'policy'


@pytest.mark.functional
def test_get_mention_policy_message_data_reply(
    graphql_user, graphql_organization, admin_user
):
    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(
        owner=graphql_user, content='This is a test comment'
    )

    PolicyComment.objects.create(comment=comment, policy=policy)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    mention = Mention.objects.create(user=graphql_user, comment=comment, reply=reply)

    result = mention.get_mention_policy_message_data()

    assert result['policy'].name == 'Policy'
    assert result['message_content'] == 'Reply test'


@pytest.mark.functional
def test_get_mention_policy_message_data_comment(
    graphql_user, graphql_organization, admin_user
):
    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(
        owner=graphql_user, content='This is a test comment'
    )

    PolicyComment.objects.create(comment=comment, policy=policy)

    mention = Mention.objects.create(user=graphql_user, comment=comment)

    result = mention.get_mention_policy_message_data()

    assert result['policy'].name == 'Policy'
    assert result['message_content'] == 'This is a test comment'


@pytest.mark.functional
@freeze_time(CURRENT_TIME)
@patch('alert.utils.send_alert_email')
def test_create_policy_mention_alerts_comment(
    send_alert_email, graphql_user, graphql_organization, admin_user
):
    graphql_user.user_preferences['profile']['alerts'] = ALERT_PREFERENCES[
        'IMMEDIATELY'
    ]
    graphql_user.save()

    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(owner=admin_user, content='This is a test comment')

    PolicyComment.objects.create(comment=comment, policy=policy)

    mention = Mention.objects.create(user=graphql_user, comment=comment)

    create_policy_mention_alerts([mention])

    assert send_alert_email.delay.call_count == 1
    send_alert_email.delay.assert_called_with(
        {
            'to': 'test@heylaika.com',
            'subject': ' mentioned you in a comment in Policy.',
            'template_context': {
                'alerts': [
                    {
                        'sender_name': '',
                        'message_owner': '',
                        'alert_action': 'mentioned you in a comment:',
                        'created_at': CURRENT_TIME.isoformat(),
                        'content': 'This is a test comment',
                        'entity_name': 'Policy',
                        'page_section': 'Policies',
                    }
                ],
                'call_to_action_url': f'http://localhost:3000/policies/{policy.id}',
            },
        },
        ALERT_EMAIL_TEMPLATES['COMMENTS'],
    )


@pytest.mark.functional
@freeze_time(CURRENT_TIME)
@patch('alert.utils.send_alert_email')
def test_create_policy_mention_alerts_reply(
    send_alert_email, graphql_user, graphql_organization, admin_user
):
    graphql_user.user_preferences['profile']['alerts'] = ALERT_PREFERENCES[
        'IMMEDIATELY'
    ]
    graphql_user.save()

    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(owner=admin_user, content='This is a test comment')

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    PolicyComment.objects.create(comment=comment, policy=policy)

    mention = Mention.objects.create(user=graphql_user, comment=comment, reply=reply)

    create_policy_mention_alerts([mention])

    assert send_alert_email.delay.call_count == 1
    send_alert_email.delay.assert_called_with(
        {
            'to': 'test@heylaika.com',
            'subject': ' replied to your comment in Policy.',
            'template_context': {
                'alerts': [
                    {
                        'sender_name': '',
                        'message_owner': '',
                        'alert_action': 'replied to a comment:',
                        'created_at': CURRENT_TIME.isoformat(),
                        'content': 'Reply test',
                        'entity_name': 'Policy',
                        'page_section': 'Policies',
                    }
                ],
                'call_to_action_url': f'http://localhost:3000/policies/{policy.id}',
            },
        },
        ALERT_EMAIL_TEMPLATES['COMMENTS'],
    )


@pytest.mark.functional
@freeze_time(CURRENT_TIME)
@patch('alert.utils.send_alert_email')
def test_notify_add_policy_reply(
    send_alert_email, graphql_user, graphql_organization, admin_user
):
    graphql_user.user_preferences['profile']['alerts'] = ALERT_PREFERENCES[
        'IMMEDIATELY'
    ]
    graphql_user.save()

    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(owner=admin_user, content='This is a test comment')

    reply = Reply.objects.create(
        owner=graphql_user, parent=comment, content='Reply test'
    )

    PolicyComment.objects.create(comment=comment, policy=policy)

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['POLICY_REPLY']
    )

    notify_add_policy_reply(alert, reply)

    assert send_alert_email.delay.call_count == 1
    send_alert_email.delay.assert_called_with(
        {
            'to': 'admin@example.com',
            'subject': ' replied to your comment in Policy.',
            'template_context': {
                'alerts': [
                    {
                        'sender_name': '',
                        'message_owner': '',
                        'alert_action': 'replied to a comment:',
                        'created_at': CURRENT_TIME.isoformat(),
                        'content': 'Reply test',
                        'entity_name': 'Policy',
                        'page_section': 'Policies',
                    }
                ],
                'call_to_action_url': f'http://localhost:3000/policies/{policy.id}',
            },
        },
        ALERT_EMAIL_TEMPLATES['COMMENTS'],
    )


@pytest.mark.functional(permissions=['comment.delete_reply'])
def test_delete_reply(graphql_client, comment, reply):
    expected_is_delete_state = True
    delete_reply_input = {
        'input': dict(
            replyId=reply.id,
            commentId=comment.id,
        )
    }
    graphql_client.execute(DELETE_REPLY, variables=delete_reply_input)
    reply = Reply.objects.get(id=reply.id)
    assert reply.is_deleted == expected_is_delete_state


@pytest.mark.functional(permissions=['comment.change_reply'])
def test_update_reply(graphql_client, comment, reply):
    expected_edit_reply_content = 'Test reply 2'
    update_reply_input = {
        'input': dict(replyId=reply.id, content=expected_edit_reply_content)
    }
    graphql_client.execute(UPDATE_REPLY, variables=update_reply_input)
    reply = Reply.objects.get(id=reply.id)
    assert reply.content == expected_edit_reply_content


@pytest.mark.functional(permissions=['comment.add_reply'])
def test_add_reply(graphql_client, graphql_user, control, control_comment):
    expected_reply = 'Trying reply on comment'
    add_reply_input = {
        'input': dict(
            content=expected_reply,
            objectId=control.id,
            objectType=CONTROL,
            commentId=control_comment.id,
        )
    }

    graphql_client.execute(ADD_REPLY, variables=add_reply_input)
    comment = Control.objects.get(id=control.id).comments.first()
    reply = comment.replies.first()
    assert reply.content == expected_reply
    assert reply.owner == graphql_user


@pytest.mark.functional(permissions=['comment.add_reply'])
def test_add_reply_with_tagged_users(
    graphql_client, graphql_user, control, control_comment
):
    expected_reply = 'Trying reply on comment with users'
    add_reply_input = {
        'input': dict(
            content=expected_reply,
            objectId=control.id,
            commentId=control_comment.id,
            objectType=CONTROL,
            taggedUsers=[graphql_user.email, graphql_user.email],
        )
    }

    graphql_client.execute(ADD_REPLY, variables=add_reply_input)
    comment = Control.objects.get(id=control.id).comments.first()
    reply = comment.replies.first()
    mention = reply.mentions.first()

    assert reply.content == expected_reply
    assert mention.user == graphql_user


DELETE_COMMENT = '''
    mutation deleteComment($input: DeleteCommentInput!) {
      deleteComment(input: $input) {
        comment{
            id
        }
      }
    }
'''


@pytest.mark.functional(permissions=['comment.delete_comment'])
def test_check_deleted_comments(graphql_client, control, control_comment):
    delete_control_input = {
        'input': dict(
            objectId=control.id,
            objectType=CONTROL,
            commentId=control_comment.id,
        )
    }
    graphql_client.execute(DELETE_COMMENT, variables=delete_control_input)
    comment = Comment.objects.get(id=control_comment.id)
    assert comment.is_deleted


@pytest.mark.functional(permissions=['comment.add_comment'])
def test_add_comment(graphql_client, graphql_user, control):
    expected_comment = 'Trying comment without tagged'
    add_comment_input = {
        'input': dict(
            content=expected_comment, objectId=control.id, objectType='control'
        )
    }

    graphql_client.execute(ADD_COMMENT, variables=add_comment_input)

    comment = Control.objects.get(id=control.id).comments.first()

    assert comment.content == expected_comment
    assert comment.owner == graphql_user


@pytest.mark.functional(permissions=['comment.add_comment'])
def test_add_comment_with_tagged_users(graphql_client, control, user):
    test_content = 'Testing a new tagged user @JohnDoe'
    comment_input = {
        'input': dict(
            content=test_content,
            objectId=control.id,
            objectType='control',
            taggedUsers=['miguel+test@heylaika.com'],
        )
    }
    graphql_client.execute(ADD_COMMENT, variables=comment_input)

    comment = Control.objects.get(id=control.id).comments.first()
    mention = comment.mentions.first()
    assert comment.content == test_content
    assert mention.user == user


@pytest.mark.functional(permissions=['comment.add_comment'])
def test_add_comment_or_reply_with_tagged_users_comment(
    graphql_client, graphql_organization, graphql_user, user
):
    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    test_content = 'Testing a new tagged user @JohnDoe'
    comment_input = {
        'input': dict(
            content=test_content,
            objectId=policy.id,
            objectType='policy',
            taggedUsers=['miguel+test@heylaika.com'],
            actionId='',
        )
    }
    graphql_client.execute(ADD_COMMENT_OR_REPLY, variables=comment_input)

    comment = Policy.objects.get(id=policy.id).policy_comments.first().comment

    assert comment.content == 'Testing a new tagged user @JohnDoe'
    assert comment.mentions.first().user.email == 'miguel+test@heylaika.com'


@pytest.mark.functional(permissions=['comment.add_comment'])
def test_add_comment_or_reply_with_tagged_users_reply(
    graphql_client, graphql_organization, graphql_user, user
):
    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    test_content = 'Testing a new tagged user @JohnDoe'
    comment_input = {
        'input': dict(
            content=test_content,
            objectId=policy.id,
            objectType='policy',
            taggedUsers=['miguel+test@heylaika.com'],
            actionId='',
        )
    }
    graphql_client.execute(ADD_COMMENT_OR_REPLY, variables=comment_input)

    comment = Policy.objects.get(id=policy.id).policy_comments.first().comment

    test_content = 'Testing reply @JohnDoe'
    comment_input = {
        'input': dict(
            content=test_content,
            objectId=policy.id,
            objectType='policy',
            taggedUsers=['test@heylaika.com'],
            actionId=comment.action_id,
        )
    }
    graphql_client.execute(ADD_COMMENT_OR_REPLY, variables=comment_input)

    assert comment.content == 'Testing a new tagged user @JohnDoe'
    assert comment.mentions.first().user.email == 'miguel+test@heylaika.com'
    assert comment.replies.first().content == 'Testing reply @JohnDoe'
    assert comment.replies.first().owner.email == 'test@heylaika.com'


UPDATE_COMMENT = '''
    mutation updateComment($input: UpdateCommentInput!) {
      updateComment(input: $input) {
        comment {
            id
            content
            state
        }
      }
    }
'''

UPDATE_COMMENT_STATE = '''
    mutation updateCommentState($input: UpdateCommentStateInput!) {
    updateCommentState(input: $input) {
      comment {
        id
        content
        state
      }
    }
  }
'''


@pytest.mark.functional(permissions=['comment.change_comment'])
def test_update_comment(graphql_client, control_comment, control):
    expected_content = 'new content'
    update_control_input = {
        'input': dict(
            content=expected_content,
            objectId=control.id,
            commentId=control_comment.id,
            objectType='control',
        )
    }
    graphql_client.execute(UPDATE_COMMENT, variables=update_control_input)
    comment = Comment.objects.get(id=control_comment.id)
    assert comment.content == expected_content


@pytest.mark.functional(permissions=['comment.change_comment'])
def test_update_comment_to_resolved(graphql_client, control_comment, control):
    update_comment_input = {
        'input': dict(
            objectId=control.id,
            commentId=control_comment.id,
            objectType='control',
            state=RESOLVED,
        )
    }

    response = graphql_client.execute(
        UPDATE_COMMENT_STATE, variables=update_comment_input
    )
    assert response['data']['updateCommentState']['comment']['state'] == RESOLVED


@pytest.mark.functional(permissions=['comment.change_comment'])
def test_update_comment_to_unresolved(graphql_client, control_comment, control):
    update_comment_input = {
        'input': dict(
            objectId=control.id,
            commentId=control_comment.id,
            objectType='control',
            state=UNRESOLVED,
        )
    }

    response = graphql_client.execute(
        UPDATE_COMMENT_STATE, variables=update_comment_input
    )
    assert response['data']['updateCommentState']['comment']['state'] == UNRESOLVED


@pytest.mark.functional(permissions=['comment.change_comment'])
def test_update_comment_with_tagged_users(
    graphql_client, control_comment, control, user
):
    test_content = 'Testing a new tagged user @JohnDoe'
    comment_input = {
        'input': dict(
            content=test_content,
            objectId=control.id,
            commentId=control_comment.id,
            objectType='control',
            taggedUsers=['miguel+test@heylaika.com'],
        )
    }
    graphql_client.execute(UPDATE_COMMENT, variables=comment_input)
    comment = Control.objects.get(id=control.id).comments.first()
    mention = comment.mentions.first()
    assert comment.content == test_content
    assert mention.user == user
