import pytest

from alert.constants import ALERT_TYPES
from alert.models import Alert
from comment.models import Comment, CommentAlert, Mention, Reply
from program.models import SubTask, SubtaskAlert, TaskComment
from program.tests import (
    CREATE_SUBTASK_WITH_ASSIGNEE,
    GET_ALERTS_QUERY,
    GET_HAS_NEW_ALERTS,
    GET_TASK_COMMENTS,
    UPDATE_ALERT_VIEWED,
    UPDATE_SUBTASK,
    UPDATE_SUBTASK_STATUS,
    create_program,
    create_task,
)
from user.tests import create_user


@pytest.fixture
def program(graphql_organization):
    return create_program(
        organization=graphql_organization,
        name='Privacy Program',
        description='This is an example of program',
    )


@pytest.fixture
def task(graphql_organization, program):
    return create_task(organization=graphql_organization, program=program)


@pytest.fixture
def user(graphql_organization):
    return create_user(graphql_organization, [], 'johndoe@heylaika.com')


@pytest.fixture
def user2(graphql_organization):
    user = create_user(graphql_organization, [], 'user2@mail.com')
    return user


@pytest.fixture
def subtask(graphql_user, task):
    return SubTask.objects.create(
        task=task,
        text='Subtask 1',
        status='completed',
        group='documentation',
        assignee=graphql_user,
    )


@pytest.fixture
def comment(graphql_user, task):
    comment = Comment.objects.create(owner=graphql_user, content='test comment')

    TaskComment.objects.create(task=task, comment=comment)
    return comment


@pytest.fixture
def reply(graphql_user, task, comment):
    reply = Reply.objects.create(
        owner=graphql_user, content='test reply', parent=comment
    )

    comment.replies.add(reply)
    return reply


@pytest.fixture
def alert(graphql_organization, graphql_user):
    sender = create_user(graphql_organization, [], 'sender@mail.com')
    return Alert.objects.create(sender=sender, receiver=graphql_user, type='MENTION')


@pytest.mark.functional(permissions=['program.view_task'])
def test_get_task_comments(
    graphql_client, graphql_organization, graphql_user, program, task, subtask
):
    expected_comment = 'Testing getting task comments'
    comment = Comment.objects.create(owner=graphql_user, content=expected_comment)
    task.comments.set([comment])
    response = graphql_client.execute(GET_TASK_COMMENTS, variables={'id': str(task.id)})
    comments = response['data']['task']['comments']

    assert len(comments) == 1
    assert comments[0]['content'] == expected_comment


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_query_get_alerts(
    graphql_client,
    graphql_organization,
    task,
    user2,
    graphql_user,
    subtask,
):
    comment = Comment.objects.create(owner=user2, content='test comment')

    TaskComment.objects.create(task=task, comment=comment)

    mention = Mention.objects.create(user=graphql_user, comment=comment)
    room_id = mention.user.organization.id
    mention.create_mention_alert(room_id)
    # Create subtask alert
    subtask_alert = Alert.objects.create(
        sender=user2, receiver=graphql_user, type=ALERT_TYPES.get('NEW_ASSIGNMENT')
    )

    SubtaskAlert.objects.create(
        alert=subtask_alert,
        subtask=subtask,
    )

    # Create resolve alert
    resolve_alert = Alert.objects.create(
        sender=user2, receiver=graphql_user, type=ALERT_TYPES.get('RESOLVE')
    )

    CommentAlert.objects.create(alert=resolve_alert, comment=comment)

    response = graphql_client.execute(GET_ALERTS_QUERY)
    alerts = response['data']['alerts']['data']
    pagination = response['data']['alerts']['pagination']

    assert len(alerts) == 3
    assert not pagination['hasNext']
    assert pagination['pageSize'] == 12


@pytest.mark.functional(permissions=['alert.change_alert'])
def test_update_alerts_viewed(
    graphql_client,
    graphql_user,
    alert,
):
    expected_viewed_value = True
    expected_response_status = True

    response = graphql_client.execute(UPDATE_ALERT_VIEWED)
    response_status = response['data']['updateAlertViewed']['success']

    updated_alert = Alert.objects.get(receiver=graphql_user)

    assert response_status == expected_response_status
    assert updated_alert.viewed == expected_viewed_value


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_has_new_alerts(
    graphql_client,
    alert,
):
    expected_result = True
    response = graphql_client.execute(GET_HAS_NEW_ALERTS)

    has_new_alerts = response['data']['hasNewAlerts']

    assert has_new_alerts == expected_result


@pytest.mark.functional(permissions=['program.add_subtask'])
def test_create_subtask_assignee(
    graphql_client,
    task,
    graphql_user,
):
    create_subtask_input = {
        'input': dict(
            assigneeEmail=graphql_user.email,
            badges='',
            dueDate='2021-02-09',
            group='documentation',
            priority='key',
            requiresEvidence=False,
            taskId=task.id,
            text='subtask assignee',
        )
    }

    subtask_response = graphql_client.execute(
        CREATE_SUBTASK_WITH_ASSIGNEE, variables=create_subtask_input
    )

    subtask_with_assignee = subtask_response['data']
    assert len(subtask_with_assignee) == 1


@pytest.mark.functional(permissions=['program.change_subtask', 'program.add_subtask'])
def test_update_subtask(
    graphql_client,
    task,
    graphql_user,
    user2,
    subtask,
    graphql_organization,
):
    update_subtask_input = {
        'input': dict(
            assigneeEmail=user2.email,
            dueDate=subtask.due_date,
            group=subtask.group,
            priority=subtask.priority,
            requiresEvidence=subtask.requires_evidence,
            badges="",
            text=subtask.text,
            id=str(subtask.id),
        )
    }

    subtask_response = graphql_client.execute(
        UPDATE_SUBTASK, variables=update_subtask_input
    )

    updated_subtask = subtask_response['data']['updateSubtask']['subtask']

    assert updated_subtask['assignee']['email'] == user2.email


@pytest.mark.functional(permissions=['program.change_subtask_partial'])
def test_update_subtask_status(
    graphql_client, task, subtask, graphql_user, graphql_organization
):
    subtask_id = str(subtask.id)
    expected_status = 'not_applicable'

    update_status_input = {
        'input': dict(
            id=subtask_id,
            status=expected_status,
            completedAt='2021-02-5',
        )
    }
    graphql_client.execute(UPDATE_SUBTASK_STATUS, variables=update_status_input)

    updated_subtask = SubTask.objects.get(id=subtask_id)
    assert updated_subtask.status == expected_status
