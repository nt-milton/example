import pytest

from alert.models import Alert
from comment.models import Comment, Reply
from control.models import ControlComment
from control.tests import create_control
from user.tests import create_user


@pytest.fixture
def control(graphql_organization):
    return create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control test',
        description='Test Description',
    )


@pytest.fixture
def user(graphql_organization):
    return create_user(graphql_organization, [], 'miguel+test@heylaika.com')


@pytest.fixture
def comment(graphql_user, control):
    comment = Comment.objects.create(owner=graphql_user, content='test comment')

    ControlComment.objects.create(control=control, comment=comment)
    return comment


@pytest.fixture
def reply(graphql_user, comment):
    reply = Reply.objects.create(
        owner=graphql_user, content='test reply', parent=comment
    )

    comment.replies.add(reply)
    return reply


@pytest.fixture
def alert(graphql_organization, graphql_user):
    sender = create_user(graphql_organization, [], 'sender@mail.com')
    return Alert.objects.create(sender=sender, receiver=graphql_user, type='MENTION')
