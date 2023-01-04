import logging

import pytest

from alert.constants import ALERT_TYPES
from alert.models import Alert
from alert.utils_policy import (
    build_policy_mention,
    build_policy_reply,
    get_policy_alerts_template_context,
)
from comment.models import Comment, CommentAlert, Mention, Reply, ReplyAlert
from control.models import ControlComment
from policy.models import PolicyComment
from policy.tests.factory import create_empty_policy


def create_alert(user, **kwargs):
    return Alert.objects.create(sender=user, receiver=user, **kwargs)


def create_comment(user, **kwargs):
    return Comment.objects.create(owner=user, **kwargs)


def create_replay(user, **kwargs):
    return Reply.objects.create(owner=user, **kwargs)


def create_reply_alert(alert, reply):
    return ReplyAlert.objects.create(
        alert=alert,
        reply=reply,
    )


def create_control_comment(control, comment):
    return ControlComment.objects.create(control=control, comment=comment)


def create_mention(user, **kwargs):
    return Mention.objects.create(user=user, **kwargs)


def create_comment_mention(alert, comment):
    CommentAlert.objects.create(
        alert=alert,
        comment=comment,
    )


def create_policy_comment(policy, comment):
    return PolicyComment.objects.create(policy=policy, comment=comment)


@pytest.mark.functional
def test_build_policy_reply(graphql_user, graphql_organization):
    reply_comment = 'My reply'
    comment_content = 'My comment'

    graphql_user.first_name = 'userName'
    graphql_user.last_name = 'userLastname'
    graphql_user.save()

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('CONTROL_REPLY'))

    comment = create_comment(user=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    create_policy_comment(policy=policy, comment=comment)

    reply = create_replay(user=graphql_user, content=reply_comment, parent=comment)

    create_reply_alert(alert=alert, reply=reply)

    actual = build_policy_reply(alert=alert)

    expected = {
        'message_owner': 'Username Userlastname',
        'content': 'My reply',
        'entity_name': 'Policy test',
    }

    assert actual == expected


@pytest.mark.functional
def test_build_policy_mention_based_reply(graphql_user, graphql_organization):
    reply_comment = 'My reply'
    comment_content = 'My comment'

    graphql_user.first_name = 'userName'
    graphql_user.last_name = 'userLastname'
    graphql_user.save()

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    comment = create_comment(user=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    create_policy_comment(policy=policy, comment=comment)

    reply = create_replay(user=graphql_user, content=reply_comment, parent=comment)

    create_reply_alert(alert=alert, reply=reply)

    create_mention(user=graphql_user, comment=comment, reply=reply)

    actual = build_policy_mention(alert=alert)

    expected = {
        'message_owner': 'Username Userlastname',
        'content': 'My reply',
        'entity_name': 'Policy test',
    }

    assert actual == expected


@pytest.mark.functional
def test_build_policy_mention_based_comment(graphql_user, graphql_organization):
    reply_comment = 'My reply'
    comment_content = 'My comment'

    graphql_user.first_name = 'userName'
    graphql_user.last_name = 'userLastname'
    graphql_user.save()

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    comment = create_comment(user=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    create_policy_comment(policy=policy, comment=comment)

    reply = create_replay(user=graphql_user, content=reply_comment, parent=comment)

    create_comment_mention(
        alert=alert,
        comment=comment,
    )

    create_mention(user=graphql_user, comment=comment, reply=reply)

    actual = build_policy_mention(alert=alert)

    expected = {
        'message_owner': 'Username Userlastname',
        'content': 'My comment',
        'entity_name': 'Policy test',
    }

    assert actual == expected


@pytest.mark.functional
def test_get_policy_alerts_template_context(graphql_user, graphql_organization):
    reply_comment = 'My reply'
    comment_content = 'My comment'

    graphql_user.first_name = 'userName'
    graphql_user.last_name = 'userLastname'
    graphql_user.save()

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    comment = create_comment(user=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    create_policy_comment(policy=policy, comment=comment)

    reply = create_replay(user=graphql_user, content=reply_comment, parent=comment)

    create_comment_mention(
        alert=alert,
        comment=comment,
    )

    create_mention(user=graphql_user, comment=comment, reply=reply)

    alert2 = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_REPLY'))

    create_reply_alert(alert=alert2, reply=reply)

    actual = get_policy_alerts_template_context(alerts=[alert, alert2], logger=None)

    expected = [
        {
            'sender_name': 'Username Userlastname',
            'alert_action': 'mentioned you in a comment:',
            'created_at': alert.created_at,
            'page_section': 'Policy',
            'message_owner': 'Username Userlastname',
            'content': 'My comment',
            'entity_name': 'Policy test',
        },
        {
            'sender_name': 'Username Userlastname',
            'alert_action': 'replied to a comment:',
            'created_at': alert2.created_at,
            'page_section': 'Policy',
            'message_owner': 'Username Userlastname',
            'content': 'My reply',
            'entity_name': 'Policy test',
        },
    ]

    assert actual == expected


@pytest.mark.functional
def test_build_policy_mention_based_none(graphql_user, graphql_organization):
    reply_comment = 'My reply'
    comment_content = 'My comment'

    graphql_user.first_name = 'userName'
    graphql_user.last_name = 'userLastname'
    graphql_user.save()

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    comment = create_comment(user=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    create_policy_comment(policy=policy, comment=comment)

    reply = create_replay(user=graphql_user, content=reply_comment, parent=comment)

    create_mention(user=graphql_user, comment=comment, reply=reply)

    with pytest.raises(ValueError) as exc_info:
        build_policy_mention(alert=alert)

    assert str(exc_info.value) == 'Reply or Comment missing'


@pytest.mark.functional
def test_get_policy_alerts_template_context_one_reply_error(
    graphql_user, graphql_organization
):
    reply_comment = 'My reply'
    comment_content = 'My comment'

    graphql_user.first_name = 'userName'
    graphql_user.last_name = 'userLastname'
    graphql_user.save()

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    comment = create_comment(user=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    create_policy_comment(policy=policy, comment=comment)

    reply = create_replay(user=graphql_user, content=reply_comment, parent=comment)

    create_comment_mention(
        alert=alert,
        comment=comment,
    )

    create_mention(user=graphql_user, comment=comment, reply=reply)

    alert2 = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_REPLY'))

    alert3 = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_REPLY'))

    create_reply_alert(alert=alert3, reply=reply)

    actual = get_policy_alerts_template_context(
        alerts=[alert, alert2, alert3], logger=logging.getLogger('test')
    )

    expected = [
        {
            'sender_name': 'Username Userlastname',
            'alert_action': 'mentioned you in a comment:',
            'created_at': alert.created_at,
            'page_section': 'Policy',
            'message_owner': 'Username Userlastname',
            'content': 'My comment',
            'entity_name': 'Policy test',
        },
        {
            'sender_name': 'Username Userlastname',
            'alert_action': 'replied to a comment:',
            'created_at': alert3.created_at,
            'page_section': 'Policy',
            'message_owner': 'Username Userlastname',
            'content': 'My reply',
            'entity_name': 'Policy test',
        },
    ]

    assert actual == expected


@pytest.mark.functional
def test_get_policy_alerts_template_context_one_mention_error(
    graphql_user, graphql_organization
):
    reply_comment = 'My reply'
    comment_content = 'My comment'

    graphql_user.first_name = 'userName'
    graphql_user.last_name = 'userLastname'
    graphql_user.save()

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    comment = create_comment(user=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    create_policy_comment(policy=policy, comment=comment)

    reply = create_replay(user=graphql_user, content=reply_comment, parent=comment)

    create_comment_mention(
        alert=alert,
        comment=comment,
    )

    create_mention(user=graphql_user, comment=comment, reply=reply)

    alert2 = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    alert3 = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    create_reply_alert(alert=alert3, reply=reply)

    actual = get_policy_alerts_template_context(
        alerts=[alert, alert2, alert3], logger=logging.getLogger('test')
    )

    expected = [
        {
            'sender_name': 'Username Userlastname',
            'alert_action': 'mentioned you in a comment:',
            'created_at': alert.created_at,
            'page_section': 'Policy',
            'message_owner': 'Username Userlastname',
            'content': 'My comment',
            'entity_name': 'Policy test',
        },
        {
            'sender_name': 'Username Userlastname',
            'alert_action': 'mentioned you in a comment:',
            'created_at': alert3.created_at,
            'page_section': 'Policy',
            'message_owner': 'Username Userlastname',
            'content': 'My reply',
            'entity_name': 'Policy test',
        },
    ]

    assert actual == expected
