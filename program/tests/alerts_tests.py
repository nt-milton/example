import pytest

from alert.models import Alert
from alert.tests.factory import create_comment
from comment.models import CommentAlert
from dashboard.tests.factory import create_subtask
from program.tests import create_task
from user.tests import create_user


@pytest.fixture
def subtask(graphql_user, task):
    return create_subtask(graphql_user, task)


@pytest.fixture
def task(graphql_organization):
    return create_task(organization=graphql_organization)


@pytest.fixture
def user2(graphql_organization):
    user = create_user(graphql_organization, [], 'user2@mail.com')
    return user


@pytest.fixture
def comment(graphql_organization, graphql_user, task, subtask):
    return create_comment(
        organization=graphql_organization,
        owner=graphql_user,
        content='This is a comment',
        task_id=task.id,
        subtask_id=subtask.id,
    )


@pytest.mark.functional
def test_update_comment_status(
    graphql_user,
    comment,
    user2,
    graphql_organization,
):
    comment.create_resolve_comment_alert(
        room_id=graphql_organization,
    )

    alerts_count = Alert.objects.count()
    comment_alert = CommentAlert.objects.count()

    assert alerts_count == 1
    assert comment_alert == 1
