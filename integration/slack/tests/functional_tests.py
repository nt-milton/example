import re
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from django.db.models import QuerySet
from httmock import HTTMock, response, urlmatch

from alert.models import Alert
from comment.models import Comment, CommentAlert, Mention, Reply, ReplyAlert
from comment.tests.mutations import ADD_COMMENT
from control.models import Control, ControlComment
from control.tests import create_control
from integration import slack
from integration.models import PENDING, SUCCESS, ConnectionAccount
from integration.slack.tests.fake_api import (
    SLACK_CONFIGURATION_STATE,
    fake_slack_api,
    get_notification_preferences,
)
from integration.tests import create_request_for_callback
from integration.tests.factory import create_connection_account
from integration.views import oauth_callback
from objects.models import LaikaObject
from objects.system_types import USER, resolve_laika_object_type
from program.models import Program, SubTask, SubtaskAlert, Task, TaskComment
from user.tests import create_user

from ...constants import ERROR
from ...error_codes import (
    ACCESS_REVOKED,
    CONNECTION_TIMEOUT,
    EXPIRED_TOKEN,
    INSUFFICIENT_PERMISSIONS,
    NONE,
    PROVIDER_SERVER_ERROR,
)
from ...exceptions import ConfigurationError, TimeoutException
from ..implementation import SLACK_SYSTEM, add_channels_to_targets, get_slack_targets
from ..mapper import map_users_to_laika_object
from ..rest_client import send_slack_message
from ..types import SLACK_ALERT_TYPES, SlackAlert
from ..utils import (
    LAIKA_WEB_URL,
    get_alert_task_url,
    get_audit_message,
    get_control_mention_message,
    get_control_reply_message,
    get_discovery_data,
    get_discovery_message,
    get_mention_message,
    get_new_assignment_message,
    get_reply_message,
    replace_mentioned_emails_with_names,
)
from .test_user_maps_correctly import load_response

BALLOON_NEW_REPLY = "*:speech_balloon: New Reply*"

SLACK_USER = 'Slack User'

TASK_FOR_TESTING = 'Task for testing'

PROGRAM_FOR_TESTING = 'Program for testing'

INTEGRATION_USER = 'Integration User'


@pytest.fixture
def connection_account():
    with fake_slack_api():
        yield slack_connection_account()


@pytest.fixture
def connection_account_active(graphql_organization):
    with fake_slack_api():
        yield slack_connection_account_configured(organization=graphql_organization)


@pytest.fixture
def control(graphql_organization):
    return create_control(
        organization=graphql_organization,
        display_id=1,
        name='Slack Control test',
        description='Test Description',
    )


@pytest.fixture
def slack_user(graphql_organization):
    return create_user(
        organization=graphql_organization,
        email='slackuser+test@heylaika.com',
        first_name='Slack',
        last_name='User',
    )


@pytest.fixture
def customer_user(graphql_organization):
    return create_user(
        organization=graphql_organization,
        email='myboss@company.com',
        first_name='Boss',
        last_name='Test',
    )


@pytest.fixture
def get_custom_alert_mock(slack_user, customer_user):
    def create_alert(alert_type: str):
        return Alert.objects.create(
            type=alert_type,
            viewed=False,
            sender=slack_user,
            receiver=customer_user,
        )

    return create_alert


@pytest.fixture
def create_comment_alert_mock(comment_and_reply_mention):
    def create_comment_alert(alert: SlackAlert):
        return CommentAlert.objects.create(
            alert=alert, comment=comment_and_reply_mention.get('comment')
        )

    return create_comment_alert


@pytest.fixture
def create_comment_alert_mock_wo_mention(comment_and_reply_wo_mention):
    def create_comment_alert(alert: SlackAlert):
        return CommentAlert.objects.create(
            alert=alert, comment=comment_and_reply_wo_mention.get('comment')
        )

    return create_comment_alert


@pytest.fixture
def create_reply_alert_mock(comment_and_reply_mention):
    def create_reply_alert(alert: SlackAlert):
        return ReplyAlert.objects.create(
            alert=alert, reply=comment_and_reply_mention.get('reply')
        )

    return create_reply_alert


@pytest.fixture
def create_reply_alert_mock_wo_mention(comment_and_reply_wo_mention):
    def create_reply_alert(alert: SlackAlert):
        return ReplyAlert.objects.create(
            alert=alert, reply=comment_and_reply_wo_mention.get('reply')
        )

    return create_reply_alert


@pytest.fixture
def create_control_comment_mock(slack_user, comment_and_reply_mention):
    def create_control_comment():
        control = Control.objects.create(
            organization=slack_user.organization, name='Control for testing'
        )
        return ControlComment.objects.create(
            comment=comment_and_reply_mention.get('comment'), control=control
        )

    return create_control_comment


@pytest.fixture
def create_control_reply_mock(slack_user, comment_and_reply_wo_mention):
    def create_control_comment():
        control = Control.objects.create(
            organization=slack_user.organization, name='Control for testing'
        )
        return ControlComment.objects.create(
            comment=comment_and_reply_wo_mention.get('comment'), control=control
        )

    return create_control_comment


@pytest.fixture
def comment_and_reply_mention(connection_account, slack_user) -> Dict:
    program = Program.objects.create(
        organization=connection_account.organization, name=PROGRAM_FOR_TESTING
    )
    task = Task.objects.create(program=program, name=TASK_FOR_TESTING)
    comment = Comment.objects.create(
        owner=slack_user,
        owner_name=SLACK_USER,
        content='This is the parent comment for testing',
    )
    reply = Reply.objects.create(
        owner=slack_user,
        content='This is a reply for testing',
        parent=comment,
        owner_name=SLACK_USER,
    )
    TaskComment.objects.create(comment=comment, task=task)
    Mention.objects.create(user=slack_user, comment=comment, reply=reply)
    return {'comment': comment, 'reply': reply}


@pytest.fixture
def comment_and_reply_wo_mention(connection_account, slack_user) -> Dict:
    program = Program.objects.create(
        organization=connection_account.organization, name=PROGRAM_FOR_TESTING
    )
    task = Task.objects.create(program=program, name=TASK_FOR_TESTING)
    comment = Comment.objects.create(
        owner=slack_user,
        owner_name=SLACK_USER,
        content='This is the parent comment for testing',
    )
    reply = Reply.objects.create(
        owner=slack_user,
        content='This is a reply for testing',
        parent=comment,
        owner_name=SLACK_USER,
    )
    TaskComment.objects.create(comment=comment, task=task)
    return {'comment': comment, 'reply': reply}


@pytest.fixture
def create_slack_alert_mock(connection_account, slack_user, customer_user):
    def create_slack_alert(
        alert_type: str,
        quantity: int = 1,
        alert: Optional[Alert] = None,
        audit: Optional[str] = None,
    ) -> SlackAlert:
        new_alert: SlackAlert = SlackAlert(
            alert_type=alert_type,
            integration=connection_account.integration,
            quantity=quantity,
            sender=slack_user,
            receiver=customer_user,
        )
        if alert:
            new_alert.alert = alert
        if audit:
            new_alert.audit = audit
        return new_alert

    return create_slack_alert


@pytest.fixture
def user_list():
    users_response = load_response('raw_users_response.json')
    return users_response.get('members')


@pytest.mark.functional
def test_slack_integration_callback(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, SLACK_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    assert 'channels' in connection_account.configuration_state
    assert connection_account.status == PENDING


@pytest.mark.functional
def test_slack_integration_on_account_inactive(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/users.list')
    def slack_user_list(url, request):
        return response(
            status_code=200, content='{"ok":false,"error":"account_inactive"}'
        )

    with HTTMock(slack_user_list):
        with pytest.raises(ConfigurationError):
            slack.run(connection_account)

    assert connection_account.status == ERROR
    assert connection_account.error_code == ACCESS_REVOKED


@pytest.mark.functional
def test_slack_integration_on_token_expired(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/users.list')
    def slack_user_list(url, request):
        return response(status_code=200, content='{"ok":false,"error":"token_expired"}')

    with HTTMock(slack_user_list):
        with pytest.raises(ConfigurationError):
            slack.run(connection_account)

    assert connection_account.status == ERROR
    assert connection_account.error_code == EXPIRED_TOKEN


@pytest.mark.functional
def test_slack_integration_on_token_revoked(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/users.list')
    def slack_user_list(url, request):
        return response(status_code=200, content='{"ok":false,"error":"token_revoked"}')

    with HTTMock(slack_user_list):
        with pytest.raises(ConfigurationError):
            slack.run(connection_account)

    assert connection_account.status == ERROR
    assert connection_account.error_code == ACCESS_REVOKED


@pytest.mark.functional
def test_slack_integration_on_access_denied(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/users.list')
    def slack_user_list(url, request):
        return response(status_code=200, content='{"ok":false,"error":"access_denied"}')

    with HTTMock(slack_user_list):
        with pytest.raises(ConfigurationError):
            slack.run(connection_account)

    assert connection_account.status == ERROR
    assert connection_account.error_code == INSUFFICIENT_PERMISSIONS


@pytest.mark.functional
def test_slack_integration_on_no_permission(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/users.list')
    def slack_user_list(url, request):
        return response(status_code=200, content='{"ok":false,"error":"no_permission"}')

    with HTTMock(slack_user_list):
        with pytest.raises(ConfigurationError):
            slack.run(connection_account)

    assert connection_account.status == ERROR
    assert connection_account.error_code == INSUFFICIENT_PERMISSIONS


@pytest.mark.functional
def test_slack_integration_on_request_timeout(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/users.list')
    def slack_user_list(url, request):
        return response(
            status_code=200, content='{"ok":false,"error":"request_timeout"}'
        )

    # This test retries 3 times and then finally ends on errors status
    with HTTMock(slack_user_list):
        with pytest.raises(TimeoutException):
            slack.run(connection_account)

    assert connection_account.status == ERROR
    assert connection_account.error_code == CONNECTION_TIMEOUT


@pytest.mark.functional
def test_slack_integration_on_service_unavailable(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/users.list')
    def slack_user_list(url, request):
        return response(
            status_code=200, content='{"ok":false,"error":"service_unavailable"}'
        )

    with HTTMock(slack_user_list):
        with pytest.raises(ConfigurationError):
            slack.run(connection_account)

    assert connection_account.status == ERROR
    assert connection_account.error_code == PROVIDER_SERVER_ERROR


@pytest.mark.functional
def test_slack_integration_post_message(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/chat.postMessage')
    def slack_post_message(url, request):
        return response(
            status_code=200,
            content={
                "ok": 'true',
                "channel": "C1H9RESGL",
                "ts": "1503435956.000247",
                "message": {
                    "text": "Here's a message for you",
                    "username": "ecto1",
                    "bot_id": "B19LU7CSY",
                    "attachments": [
                        {
                            "text": "This is an attachment",
                            "id": 1,
                            "fallback": "This is an attachment's fallback",
                        }
                    ],
                    "type": "message",
                    "subtype": "bot_message",
                    "ts": "1503435956.000247",
                },
            },
        )

    access_token = connection_account.authentication.get('access_token')
    with HTTMock(slack_post_message):
        post_message_result = send_slack_message(access_token, 'C1H9RESGL', [])

    assert bool(post_message_result.get('ok')) is True


@pytest.mark.functional
def test_slack_integration_post_message_error(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/chat.postMessage')
    def slack_post_message_error(url, request):
        return response(
            status_code=200, content='{"ok":false,"error":"too_many_attachments"}'
        )

    access_token = connection_account.authentication.get('access_token')
    with HTTMock(slack_post_message_error):
        post_message_result = send_slack_message(access_token, 'C1H9RESGL', [])

    assert bool(post_message_result.get('ok')) is False


@pytest.mark.functional
def test_slack_integration_access_token_error(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/oauth.v2.access')
    def slack_access_token_error(url, request):
        return response(
            status_code=200, content='{"ok":false,"error":"invalid_client_id"}'
        )

    with HTTMock(slack_access_token_error):
        with pytest.raises(ConfigurationError):
            slack.callback('mock_code', 'redirect_mock', connection_account)

    assert connection_account.status == PENDING
    assert connection_account.error_code == NONE


@pytest.mark.functional
def test_slack_integration_channels_error(connection_account):
    @urlmatch(netloc=r'slack.com', path='/api/conversations.list')
    def slack_channels_error(url, request):
        return response(status_code=200, content='{"ok":false,"error":"invalid_auth"}')

    with HTTMock(slack_channels_error):
        with pytest.raises(ConfigurationError):
            slack.callback('mock_code', 'redirect_mock', connection_account)

    assert connection_account.status == PENDING
    assert connection_account.error_code == NONE


@pytest.mark.functional
def test_slack_integration_soft_delete_inactive_users(connection_account, user_list):
    organization = connection_account.organization
    deleted_user = user_list[2]
    bot_user = user_list[0]
    existing_users = [deleted_user, bot_user]
    laika_object_type = resolve_laika_object_type(organization, USER)
    for user in existing_users:
        LaikaObject.objects.create(
            object_type=laika_object_type,
            connection_account=connection_account,
            data=map_users_to_laika_object(user, connection_account.alias),
        )
    lo_users = LaikaObject.objects.filter(
        object_type=laika_object_type,
        connection_account=connection_account,
        deleted_at=None,
    ).count()
    assert lo_users == 2
    slack.run(connection_account)
    assert connection_account.status == SUCCESS
    total_users = LaikaObject.objects.filter(
        object_type=laika_object_type,
        connection_account=connection_account,
    ).count()
    assert total_users == 10
    active_users = LaikaObject.objects.filter(
        object_type=laika_object_type,
        connection_account=connection_account,
        deleted_at=None,
    ).count()
    assert active_users == 8


@pytest.mark.functional
def test_slack_alert_type_mapping(connection_account):
    alert_type = 'CONTROL_MENTION'
    slack_alert_type = SLACK_ALERT_TYPES[alert_type]
    expected = 'MENTION'
    assert slack_alert_type == expected


@pytest.mark.functional(permissions=['comment.add_comment'])
@patch('integration.slack.implementation.send_alert_to_slack')
def test_control_comment_slack_notification(
    send_alert_to_slack_mock,
    graphql_client,
    control,
    slack_user,
    connection_account_active,
):
    test_content = "@(slackuser+test@heylaika.com) testing comment"
    comment_input = {
        'input': dict(
            content=test_content,
            objectId=control.id,
            objectType='control',
            taggedUsers=['slackuser+test@heylaika.com'],
        )
    }
    graphql_client.execute(ADD_COMMENT, variables=comment_input)

    comment = Control.objects.get(id=control.id).comments.first()
    mention = comment.mentions.first()
    send_alert_to_slack_mock.assert_called_once()
    assert comment.content == test_content
    assert mention.user == slack_user


@pytest.mark.functional()
def test_comment_mentions(
    graphql_client, control, slack_user, connection_account_active
):
    test_content = 'Testing a new tagged user @(slackuser+test@heylaika.com)'
    final_content = replace_mentioned_emails_with_names(test_content)
    expected_content = 'Testing a new tagged user *`@Slack User`*'
    assert expected_content == final_content


def slack_connection_account(**kwargs):
    return create_connection_account(
        'Slack', authentication=dict(access_token='my_token'), **kwargs
    )


def slack_connection_account_configured(**kwargs):
    return create_connection_account(
        'Slack',
        authentication=dict(access_token='my_token'),
        configuration_state=SLACK_CONFIGURATION_STATE,
        status='success',
        **kwargs,
    )


@pytest.mark.functional()
def test_empty_channels_to_targets_missing_fields(connection_account):
    targets: Dict[str, Dict[str, str]] = {}
    settings = get_notification_preferences()['settings']
    preferences = settings['notificationPreferences']

    # AUDIT_COMPLETE in the file doesn't have isEnable
    targets = add_channels_to_targets(
        settings=preferences,
        targets=targets,
        alert_type='AUDIT_COMPLETE',
        connection=connection_account,
    )
    assert len(targets) == 0


@pytest.mark.functional()
def test_empty_channels_to_targets_is_enable_false(connection_account):
    targets: Dict[str, Dict[str, str]] = {}
    settings = get_notification_preferences()['settings']
    preferences = settings['notificationPreferences']

    # DRAFT_REPORT_AVAILABLE isEnable = False
    targets = add_channels_to_targets(
        settings=preferences,
        targets=targets,
        alert_type='DRAFT_REPORT_AVAILABLE',
        connection=connection_account,
    )
    assert len(targets) == 0


@pytest.mark.functional()
def test_channels_to_targets(connection_account):
    targets: Dict[str, Dict[str, str]] = {}
    settings = get_notification_preferences()['settings']
    preferences = settings['notificationPreferences']

    # AUDIT_INITIATED has all the values correctly
    targets = add_channels_to_targets(
        settings=preferences,
        targets=targets,
        alert_type='AUDIT_INITIATED',
        connection=connection_account,
    )
    assert len(targets) == 1


@pytest.mark.functional()
def test_channels_to_targets_duplicated_channel(connection_account):
    targets: Dict[str, Dict[str, str]] = {}
    settings = get_notification_preferences()['settings']
    preferences = settings['notificationPreferences']

    targets = add_channels_to_targets(
        settings=preferences,
        targets=targets,
        alert_type='AUDIT_INITIATED',
        connection=connection_account,
    )

    assert len(targets) == 1


@pytest.mark.functional()
def test_get_slack_targets_not_success_connections(connection_account):
    connection_account.status = 'error'
    connection_account.configuration_state = get_notification_preferences()
    connection_account.save()

    with patch(
        'integration.slack.implementation._get_success_connections'
    ) as error_con:
        error_con.return_value = []
        queryset_mock = MagicMock(QuerySet)
        targets = get_slack_targets(
            slack_connections=queryset_mock, alert_type='AUDIT_INITIATED'
        )
    assert len(targets) == 0


@pytest.mark.functional()
def test_get_slack_targets_with_success_connections(connection_account):
    connection_account.configuration_state = get_notification_preferences()
    connection_account.save()

    with patch(
        'integration.slack.implementation._get_success_connections'
    ) as success_conns:
        success_conns.return_value = [connection_account]
        queryset_mock = MagicMock(QuerySet)
        targets = get_slack_targets(
            slack_connections=queryset_mock, alert_type='AUDIT_INITIATED'
        )
    assert len(targets) == 1


def test_get_alert_task_url_with_values():
    alert_url = get_alert_task_url(
        url='url_test', comment_id='100', comment_state='comment_state_test'
    )
    assert (
        alert_url
        == f'{LAIKA_WEB_URL}/playbooks/url_test?'
        'commentsOpen=true&'
        'activeTab=subtasks&'
        'commentId=100&commentState=comment_state_test'
    )


def test_get_alert_task_url_without_values():
    alert_url = get_alert_task_url(
        url='url_test',
        comment_id='100',
        comment_state=None,  # Make doesn't pass the if condition
    )
    assert (
        alert_url
        == f'{LAIKA_WEB_URL}/playbooks/url_test?commentsOpen=true&activeTab=subtasks'
    )


@pytest.mark.functional()
def test_get_vendor_discovery_data(connection_account):
    expected_message = (
        '[Quantity] new '
        '*<[URL]|vendor discovered>* via your '
        f'*{connection_account.integration}* integration'
    )

    slack_alert = SlackAlert(
        alert_type='VENDOR_DISCOVERY',
        integration=connection_account.integration,
        quantity=1,
        receiver=connection_account.created_by,
    )
    url, message = get_discovery_data(slack_alert)

    assert url == f'{LAIKA_WEB_URL}/vendors?discover=1'
    assert message == expected_message


@pytest.mark.functional()
def test_get_vendors_discovery_data(connection_account):
    expected_message = (
        '[Quantity] new '
        '*<[URL]|vendors discovered>* via your '
        f'*{connection_account.integration}* integration'
    )

    slack_alert = SlackAlert(
        alert_type='VENDOR_DISCOVERY',
        integration=connection_account.integration,
        quantity=3,
        receiver=connection_account.created_by,
    )
    url, message = get_discovery_data(slack_alert)

    assert url == f'{LAIKA_WEB_URL}/vendors?discover=1'
    assert message == expected_message


@pytest.mark.functional()
def test_get_person_discovery_data(connection_account):
    expected_message = (
        '[Quantity] new '
        '<[URL]|person discovered>. '
        '\n\nPlease review and update your people table.'
    )

    slack_alert = SlackAlert(
        alert_type='PEOPLE_DISCOVERY',
        integration=connection_account.integration,
        quantity=1,
        receiver=connection_account.created_by,
    )
    url, message = get_discovery_data(slack_alert)

    assert url == f'{LAIKA_WEB_URL}/people?discover=1'
    assert message == expected_message


@pytest.mark.functional()
def test_get_people_discovery_data(connection_account):
    expected_message = (
        '[Quantity] new '
        '<[URL]|people discovered>. '
        '\n\nPlease review and update your people table.'
    )

    slack_alert = SlackAlert(
        alert_type='PEOPLE_DISCOVERY',
        integration=connection_account.integration,
        quantity=3,
        receiver=connection_account.created_by,
    )
    url, message = get_discovery_data(slack_alert)

    assert url == f'{LAIKA_WEB_URL}/people?discover=1'
    assert message == expected_message


@pytest.mark.functional()
def test_replace_mentioned_emails_with_names(slack_user, customer_user):
    comment_message = (
        '@(slackuser+test@heylaika.com) I need your help with '
        'this control, cc: @(myboss@company.com)'
    )

    comment_message = replace_mentioned_emails_with_names(comment_message)
    assert (
        comment_message
        == f'*`@{slack_user.get_full_name()}`* '
        'I need your help with this control, cc: '
        f'*`@{customer_user.get_full_name()}`*'
    )


@pytest.mark.functional()
def test_replace_mentioned_emails_invalid_user(slack_user, caplog):
    comment_message = (
        '@(slackuser+test@heylaika.com) I need your help with '
        'this control, cc: @(invaliduser@company.com)'
    )

    comment_message = replace_mentioned_emails_with_names(comment_message)
    assert (
        comment_message
        == f'*`@{slack_user.get_full_name()}`* '
        'I need your help with this control, cc: '
        '@(invaliduser@company.com)'
    )
    assert (
        'User mentioned with the email invaliduser@company.com does not exist'
        in caplog.text
    )


@pytest.fixture
def mention_alert(
    get_custom_alert_mock, create_comment_alert_mock, create_reply_alert_mock
):
    alert = get_custom_alert_mock('MENTION')
    create_comment_alert_mock(alert)
    create_reply_alert_mock(alert)
    return alert


@pytest.mark.functional()
def test_get_mention_message(create_slack_alert_mock, mention_alert):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='MENTION', alert=mention_alert
    )
    comment_regex = (
        r'\*Slack User\* mentioned \*Boss Test\* in a \*'
        f'<{LAIKA_WEB_URL}/playbooks/'
        r'[a-z0-9-]{36}/[a-z0-9-]{36}\?commentsOpen=true&'
        r'activeTab=subtasks'
        r'&commentId=1&commentState=UNRESOLVED|comment>:\*'
    )
    check_message_blocks(
        message_blocks=get_mention_message(slack_alert),
        title_message="*:speech_balloon: New Mention*",
        regex_text=comment_regex,
    )


@pytest.fixture
def control_mention_alert(
    get_custom_alert_mock,
    create_comment_alert_mock,
    create_reply_alert_mock,
    create_control_comment_mock,
):
    alert = get_custom_alert_mock('CONTROL_MENTION')
    create_comment_alert_mock(alert)
    create_reply_alert_mock(alert)
    create_control_comment_mock()
    return alert


@pytest.mark.functional()
def test_get_control_mention_message(create_slack_alert_mock, control_mention_alert):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='CONTROL_MENTION', alert=control_mention_alert
    )
    comment_regex = (
        r'\*Slack User\* mentioned \*Boss Test\* in a \*'
        f'<{LAIKA_WEB_URL}/controls/'
        r'[a-z0-9-]{36}|comment>:*\n\n> '
        r'This is a reply for testing \n\nIn the *`Control for '
        r'testing`* control'
    )
    check_message_blocks(
        message_blocks=get_control_mention_message(slack_alert),
        title_message="*:speech_balloon: New Mention*",
        regex_text=comment_regex,
    )


@pytest.fixture
def control_reply_alert(
    get_custom_alert_mock,
    create_comment_alert_mock,
    create_reply_alert_mock,
    create_control_comment_mock,
):
    alert = get_custom_alert_mock('CONTROL_REPLY')
    create_comment_alert_mock(alert)
    create_reply_alert_mock(alert)
    create_control_comment_mock()
    return alert


@pytest.fixture
def control_reply_alert_no_mention(
    get_custom_alert_mock,
    create_comment_alert_mock_wo_mention,
    create_reply_alert_mock_wo_mention,
    create_control_reply_mock,
):
    alert = get_custom_alert_mock('CONTROL_REPLY')
    create_comment_alert_mock_wo_mention(alert)
    create_reply_alert_mock_wo_mention(alert)
    create_control_reply_mock()
    return alert


@pytest.mark.functional()
def test_get_control_reply_message(create_slack_alert_mock, control_reply_alert):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='CONTROL_REPLY', alert=control_reply_alert
    )
    comment_regex = (
        r'\*Slack User\* mentioned \*Boss Test\* in a \*'
        f'<{LAIKA_WEB_URL}/controls/'
        r'[a-z0-9-]{36}|reply>\*\n\n>'
        r'This is a reply for testing \n\nIn the *`Control for '
        r'testing`* control'
    )
    check_message_blocks(
        message_blocks=get_control_reply_message(slack_alert),
        title_message=BALLOON_NEW_REPLY,
        regex_text=comment_regex,
    )


@pytest.mark.functional()
def test_get_control_reply_message_without_mention(
    create_slack_alert_mock, control_reply_alert_no_mention
):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='CONTROL_REPLY', alert=control_reply_alert_no_mention
    )
    comment_regex = (
        r'\*Slack User\* replied to a \*'
        f'<{LAIKA_WEB_URL}/controls/'
        r'[a-z0-9-]{36}|comment>\* from \*Boss Test\* \n\n>'
        r'This is a reply for testing \n\nIn the *`Control for '
        r'testing`* control'
    )
    check_message_blocks(
        message_blocks=get_control_reply_message(slack_alert),
        title_message=BALLOON_NEW_REPLY,
        regex_text=comment_regex,
    )


@pytest.fixture
def reply_alert(
    get_custom_alert_mock,
    create_comment_alert_mock,
    create_reply_alert_mock,
    create_control_comment_mock,
):
    alert = get_custom_alert_mock('REPLY')
    create_comment_alert_mock(alert)
    create_reply_alert_mock(alert)
    return alert


@pytest.mark.functional()
def test_get_reply_mention_message(create_slack_alert_mock, reply_alert):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='REPLY', alert=reply_alert
    )
    comment_regex = (
        r'\*Slack User\* replied to a '
        fr'\*<{LAIKA_WEB_URL}/playbooks/'
        r'[a-z0-9-]{36}/[a-z0-9-]{36}\?commentsOpen=true&'
        r'activeTab=subtasks'
        r'&commentId=1&commentState=UNRESOLVED|comment>\* '
        r'from \*Boss Test\*\\n\\n> This is a reply for testing '
        r'\\n\\nIn the \*`Task for testing`\* task'
    )
    check_message_blocks(
        message_blocks=get_reply_message(slack_alert),
        title_message=BALLOON_NEW_REPLY,
        regex_text=comment_regex,
    )


@pytest.fixture
def new_assignment_alert(
    connection_account, slack_user, customer_user, comment_and_reply_mention
):
    program = Program.objects.create(
        organization=connection_account.organization, name=PROGRAM_FOR_TESTING
    )
    task = Task.objects.create(program=program, name=TASK_FOR_TESTING)
    alert = Alert.objects.create(
        type='NEW_ASSIGNMENT',
        viewed=False,
        sender=slack_user,
        receiver=customer_user,
    )
    CommentAlert.objects.create(
        alert=alert, comment=comment_and_reply_mention.get('comment')
    )
    ReplyAlert.objects.create(alert=alert, reply=comment_and_reply_mention.get('reply'))
    SubtaskAlert.objects.create(
        alert=alert,
        subtask=SubTask.objects.create(
            text='Subtask for testing', group='documentation', task=task
        ),
    )
    return alert


@pytest.mark.functional()
def test_new_assignment_message(create_slack_alert_mock, new_assignment_alert):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='NEW_ASSIGNMENT',
        alert=new_assignment_alert,
    )
    check_message_blocks(
        message_blocks=get_new_assignment_message(slack_alert),
        title_message="*:ballot_box_with_check: New Assignment*",
        regex_text=r'\*Boss Test\* has been assigned a \*documentation\* '
        fr'subtask due in:\n\n> \*<{LAIKA_WEB_URL}/playbooks/'
        r'[a-z0-9-]{36}/[a-z0-9-]{36}\?commentsOpen=true&'
        r'activeTab=subtasks\|Task for testing>\*',
    )


@pytest.fixture
def audit_alert(
    get_custom_alert_mock,
    create_comment_alert_mock,
    create_reply_alert_mock,
):
    alert = get_custom_alert_mock('AUDIT_REQUESTED')
    create_comment_alert_mock(alert)
    create_reply_alert_mock(alert)
    return alert


@pytest.mark.functional()
def test_get_audit_message(create_slack_alert_mock, new_assignment_alert):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='AUDIT_REQUESTED', alert=new_assignment_alert, audit='Audit test'
    )
    check_message_blocks(
        message_blocks=get_audit_message(slack_alert),
        title_message="*:sleuth_or_spy: AUDIT REQUESTED*",
        text_message='Your organization requested a Audit test audit',
    )


@pytest.fixture
def discovery_alert(
    get_custom_alert_mock,
    create_comment_alert_mock,
    create_reply_alert_mock,
    create_control_comment_mock,
):
    alert = get_custom_alert_mock('VENDOR_DISCOVERY')
    create_comment_alert_mock(alert)
    create_reply_alert_mock(alert)
    return alert


@pytest.mark.functional()
def test_get_discovery_message(create_slack_alert_mock, new_assignment_alert):
    slack_alert: SlackAlert = create_slack_alert_mock(
        alert_type='VENDOR_DISCOVERY', alert=new_assignment_alert
    )
    check_message_blocks(
        message_blocks=get_discovery_message(slack_alert),
        title_message="*:mag: Discovery*",
        text_message=(
            f'1 new *<{LAIKA_WEB_URL}/vendors?discover=1|vendor '
            'discovered>* via your *Slack Integration* integration'
        ),
    )


def check_message_blocks(
    message_blocks: List,
    title_message: str = '',
    text_message: Optional[str] = None,
    regex_text: Optional[str] = None,
):
    title_block: Dict = message_blocks[0]
    assert title_block.get('type') == 'section'
    assert title_block.get('text') == {"type": "mrkdwn", "text": title_message}
    comment_block: Dict = message_blocks[1]
    assert comment_block.get('type', '') == 'section'
    assert comment_block.get('text', {}).get('type', '') == 'mrkdwn'
    text = comment_block.get('text', {}).get('text', '')
    if regex_text:
        assert re.match(regex_text, text)
    if text_message:
        assert text_message == text
