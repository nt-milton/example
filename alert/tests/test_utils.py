from datetime import datetime

import pytest

from action_item.models import ActionItem
from alert.constants import ALERT_EMAIL_TEMPLATES, ALERT_TYPES
from alert.models import Alert
from alert.templatetags.alert_mentions import highlight_mentions
from alert.tests.factory import (
    create_completed_audit,
    create_evidence,
    create_evidence_comment,
    create_reply,
)
from alert.utils import (
    AUDIT_ALERT_FILTER,
    COMMENT_ALERT_FILTER,
    CONTROL_ALERT_FILTER,
    calculate_surpass_alerts,
    get_action_item_from_alert,
    get_alert_email_subject,
    get_audit_from_alert,
    get_control_alert_email_subject,
    get_evidence_from_alert,
    get_policy_alert_email_subject,
    get_policy_from_alert,
    is_policy_comment_alert,
    send_alert_email,
    trim_alerts,
)
from audit.constants import AUDIT_FIRMS
from audit.models import AuditAlert
from audit.tests.factory import create_audit_firm
from comment.models import Comment, CommentAlert, Mention, Reply, ReplyAlert
from policy.models import PolicyComment
from policy.tests.factory import create_empty_policy
from user.constants import ROLE_SUPER_ADMIN
from user.models import User
from user.tests import create_user

COMMENT_CONTENT = 'This is a test comment'
ENTITY_NAME = 'Implement a formal change management process'
SENDER_NAME = 'Elvis'
MENTION_COMMENT = ' mentioned you in a comment '
MENTION_REPLY = ' replied to your comment '
DOT = '.'
IN = 'in '
REPLY_SUBJECT = SENDER_NAME + MENTION_REPLY + IN + ENTITY_NAME + DOT
MENTION_SUBJECT = SENDER_NAME + MENTION_COMMENT + IN + ENTITY_NAME + DOT


@pytest.fixture
def user(graphql_organization):
    user1 = User.objects.create(
        email='Eoghan_Hodson@mail.com',
        first_name='Eoghan',
        last_name='Hodson',
        organization=graphql_organization,
    )

    user2 = User.objects.create(
        email='paul_smith@mail.com',
        first_name='Paul Rogers',
        last_name='Smith',
        organization=graphql_organization,
    )

    return user1, user2


@pytest.fixture
def super_admin_user(graphql_organization):
    return create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='john',
        last_name='doe',
    )


@pytest.fixture
def sender(graphql_organization):
    return User.objects.create(
        first_name='John',
        last_name='Doe',
        organization=graphql_organization,
        email='sender@heylaika.com',
    )


@pytest.fixture
def audit_firm():
    return create_audit_firm(AUDIT_FIRMS[1])


@pytest.fixture
def audit(graphql_organization, audit_firm):
    return create_completed_audit(graphql_organization, audit_firm)


@pytest.fixture
def evidence(audit):
    return create_evidence(audit)


@pytest.fixture
def evidence_comment(evidence, super_admin_user, sender):
    return create_evidence_comment(super_admin_user, evidence)


@pytest.fixture
def alert_mention_evidence(graphql_organization, graphql_audit_user, sender):
    return Alert.objects.create(
        sender=sender, receiver=graphql_audit_user, type='EVIDENCE_MENTION'
    )


@pytest.fixture
def alert_mention(graphql_organization, graphql_audit_user, sender):
    return Alert.objects.create(
        sender=sender, receiver=graphql_audit_user, type='MENTION'
    )


@pytest.fixture
def alert_control_action_item(graphql_organization, graphql_audit_user, sender):
    action_item = ActionItem.objects.create(name='TEST')
    alert = Alert.objects.create(
        sender=sender,
        receiver=graphql_audit_user,
        type='CONTROL_ACTION_ITEM_ASSIGNMENT',
    )
    alert.action_items.add(action_item)
    return alert


@pytest.fixture
def reply(user, evidence_comment):
    return create_reply(user[0], evidence_comment, COMMENT_CONTENT)


@pytest.fixture
def reply_alert_evidence_mention(alert_mention_evidence, reply):
    return ReplyAlert.objects.create(alert=alert_mention_evidence, reply=reply)


@pytest.fixture
def reply_alert_mention(alert_mention, reply):
    return ReplyAlert.objects.create(alert=alert_mention, reply=reply)


@pytest.fixture
def audit_alert(audit, alert_mention):
    return AuditAlert.objects.create(alert=alert_mention, audit=audit)


def create_alert(user, **kwargs):
    return Alert.objects.create(sender=user, receiver=user, **kwargs)


def create_replay(user, **kwargs):
    return Reply.objects.create(owner=user, **kwargs)


def create_reply_alert(alert, reply):
    return ReplyAlert.objects.create(
        alert=alert,
        reply=reply,
    )


def create_mention(user, **kwargs):
    return Mention.objects.create(user=user, **kwargs)


def create_comment_mention(alert, comment):
    CommentAlert.objects.create(
        alert=alert,
        comment=comment,
    )


def test_is_policy_comment_alert():
    is_policy_comment = is_policy_comment_alert(ALERT_TYPES['POLICY_MENTION'])

    assert is_policy_comment is True


@pytest.fixture
def create_policy_and_comment(graphql_user, graphql_organization):
    comment_content = 'My comment'

    comment = Comment.objects.create(owner=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    PolicyComment.objects.create(policy=policy, comment=comment)

    return comment


@pytest.mark.functional
def test_get_policy_from_alert_mention(
    graphql_user, graphql_organization, create_policy_and_comment
):
    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    CommentAlert.objects.create(alert=alert, comment=create_policy_and_comment)

    result = get_policy_from_alert(alert)

    assert result.name == 'Policy test'


@pytest.mark.functional
def test_get_policy_from_alert_reply(
    graphql_user, graphql_organization, create_policy_and_comment
):
    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_REPLY'))

    reply = Reply.objects.create(
        content='My comment', owner=graphql_user, parent=create_policy_and_comment
    )

    ReplyAlert.objects.create(alert=alert, reply=reply)

    result = get_policy_from_alert(alert)

    assert result.name == 'Policy test'


@pytest.mark.functional
def test_format_mention_content(user):
    message = 'Hey @(eoghan_hodson@mail.com), how are you'
    assert highlight_mentions(message).find('@Eoghan Hodson')

    message = 'Hey @(paul_smith@mail.com), how are you'
    assert highlight_mentions(message).find('@Paul Smith')


@pytest.mark.functional
def test_get_alert_email_subject():
    email_subject = get_alert_email_subject(
        alert_type=ALERT_TYPES['REPLY'], sender_name=SENDER_NAME, task_name=ENTITY_NAME
    )
    assert email_subject == REPLY_SUBJECT

    email_subject = get_alert_email_subject(
        alert_type=ALERT_TYPES['MENTION'],
        sender_name=SENDER_NAME,
        task_name=ENTITY_NAME,
    )
    assert email_subject == MENTION_SUBJECT


@pytest.mark.functional
def test_get_control_alert_email_subject():
    email_subject = get_control_alert_email_subject(
        alert_type=ALERT_TYPES['CONTROL_REPLY'],
        sender_name=SENDER_NAME,
        control_name=ENTITY_NAME,
    )
    assert email_subject == REPLY_SUBJECT

    email_subject = get_control_alert_email_subject(
        alert_type=ALERT_TYPES['CONTROL_MENTION'],
        sender_name=SENDER_NAME,
        control_name=ENTITY_NAME,
    )
    assert email_subject == MENTION_SUBJECT


@pytest.mark.functional
def test_get_policy_alert_email_subject():
    email_subject = get_policy_alert_email_subject(
        alert_type=ALERT_TYPES['POLICY_REPLY'],
        sender_name=SENDER_NAME,
        policy_name=ENTITY_NAME,
    )
    assert email_subject == REPLY_SUBJECT

    email_subject = get_policy_alert_email_subject(
        alert_type=ALERT_TYPES['POLICY_MENTION'],
        sender_name=SENDER_NAME,
        policy_name=ENTITY_NAME,
    )
    assert email_subject == MENTION_SUBJECT


@pytest.mark.functional
def test_send_alert_email():
    email_info = {
        'to': 'laika@heylaika.com',
        'subject': SENDER_NAME + MENTION_COMMENT + ENTITY_NAME,
        'template_context': {
            'alerts': [
                {
                    'sender_name': SENDER_NAME,
                    'alert_action': SENDER_NAME + MENTION_COMMENT,
                    'created_at': datetime.now().isoformat(),
                    'content': 'Hey @Eoghan Hodson, how are you',
                    'entity_name': ENTITY_NAME,
                }
            ],
            'call_to_action_url': 'https://sameurl.com',
        },
    }
    result = send_alert_email.delay(email_info, ALERT_EMAIL_TEMPLATES['COMMENTS'])
    assert result.get()['success'] is True


@pytest.mark.functional
def test_get_evidence_from_evidence_comment_alert(
    alert_mention_evidence, reply_alert_evidence_mention
):
    evidence_result = get_evidence_from_alert(alert_mention_evidence)
    assert evidence_result is not None


@pytest.mark.functional
def test_get_evidence_from_audit_alert(alert_mention, reply_alert_mention):
    evidence_result = get_evidence_from_alert(alert_mention)
    assert evidence_result is not None


@pytest.mark.functional
def test_get_audit_from_evidence_comment_alert(
    alert_mention_evidence, reply_alert_evidence_mention
):
    audit_result = get_audit_from_alert(alert_mention_evidence)
    assert audit_result is not None


@pytest.mark.functional
def test_get_audit_from_audit_alert(alert_mention, reply_alert_mention, audit_alert):
    audit_result = get_audit_from_alert(alert_mention)
    assert audit_result is not None


@pytest.mark.functional
def test_get_action_item_from_alert(alert_control_action_item):
    action_item_result = get_action_item_from_alert(alert_control_action_item)
    assert action_item_result is not None


def test_comment_alert_filters():
    mention = COMMENT_ALERT_FILTER.children[0][1]
    reply = COMMENT_ALERT_FILTER.children[1][1]
    resolve = COMMENT_ALERT_FILTER.children[2][1]

    assert ALERT_TYPES['MENTION'] == ALERT_TYPES[mention]
    assert ALERT_TYPES['REPLY'] == ALERT_TYPES[reply]
    assert ALERT_TYPES['RESOLVE'] == ALERT_TYPES[resolve]


def test_audit_alert_filters():
    initiated = AUDIT_ALERT_FILTER.children[0][1]
    report_available = AUDIT_ALERT_FILTER.children[1][1]
    complete = AUDIT_ALERT_FILTER.children[2][1]

    assert ALERT_TYPES['AUDIT_INITIATED'] == ALERT_TYPES[initiated]
    assert ALERT_TYPES['DRAFT_REPORT_AVAILABLE'] == ALERT_TYPES[report_available]
    assert ALERT_TYPES['AUDIT_COMPLETE'] == ALERT_TYPES[complete]


def test_control_alert_filters():
    reply = CONTROL_ALERT_FILTER.children[0][1]
    mention = CONTROL_ALERT_FILTER.children[1][1]

    assert ALERT_TYPES['CONTROL_REPLY'] == ALERT_TYPES[reply]
    assert ALERT_TYPES['CONTROL_MENTION'] == ALERT_TYPES[mention]


@pytest.mark.functional
def test_calculate_surpass_alerts(alert_control_action_item):
    my_alert = Alert.objects.filter(type='CONTROL_ACTION_ITEM_ASSIGNMENT')

    actual_value = calculate_surpass_alerts(my_alert, my_alert, my_alert, my_alert)

    expected = 1

    assert actual_value == expected


def test_trim_alerts():
    actual_value = trim_alerts(['a', 'b', 'c', 'd', 'e'])

    expected = ['a', 'b', 'c']

    assert actual_value == expected
