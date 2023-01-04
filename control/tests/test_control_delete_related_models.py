import pytest
from django.contrib.admin.sites import AdminSite

from action_item.models import ActionItem
from alert.models import Alert
from comment.models import Comment, CommentAlert, Mention, Reply, ReplyAlert
from comment.tests.mutations import ADD_COMMENT, ADD_REPLY
from control.admin import ControlAdmin
from control.models import Control, ControlComment
from control.tests.factory import create_action_item, create_control
from control.tests.mutations import ADD_CONTROL_ACTION_ITEM, DELETE_CONTROLS
from user.tests import create_user

COMMENT_CONTENT = 'test comment'
REPLY_CONTENT = 'test reply'


class MockRequest:
    pass


@pytest.fixture()
def users(graphql_organization):
    user_1 = create_user(graphql_organization, [], 'norman@heylaika.com')
    user_2 = create_user(graphql_organization, [], 'isaza@heylaika.com')
    return user_1, user_2


@pytest.fixture()
def control(graphql_organization):
    return create_control(
        organization=graphql_organization, display_id=1, name='Control Test'
    )


@pytest.fixture()
def action_item(control):
    new_action_item = create_action_item(name="Action Item new unexpired", status="new")
    control.action_items.add(new_action_item)


def check_assertions_related_models_were_deleted():
    model_list = [
        ControlComment,
        Comment,
        Reply,
        CommentAlert,
        ReplyAlert,
        Mention,
        Alert,
    ]

    for model in model_list:
        assert model.objects.count() == 0


def create_add_comment_input(control_id, user_1_email, user_2_email):
    return {
        'input': dict(
            content=COMMENT_CONTENT,
            objectId=control_id,
            objectType='control',
            taggedUsers=[user_1_email, user_2_email],
        )
    }


def create_add_reply_input(control_id, ctrl_comment_id, user_1_email, user_2_email):
    return {
        'input': dict(
            content=REPLY_CONTENT,
            objectId=control_id,
            commentId=ctrl_comment_id,
            objectType='control',
            taggedUsers=[user_1_email, user_2_email],
        )
    }


def create_related_models_for_control(users, control_id, graphql_client):
    user_1, user_2 = users

    add_comment_input = create_add_comment_input(control_id, user_1.email, user_2.email)

    graphql_client.execute(ADD_COMMENT, variables=add_comment_input)
    ctrl_comment = Control.objects.get(id=control_id).comments.first()

    add_reply_input = create_add_reply_input(
        control_id, ctrl_comment.id, user_1.email, user_2.email
    )

    graphql_client.execute(ADD_REPLY, variables=add_reply_input)


@pytest.mark.functional(
    permissions=[
        'control.can_delete',
        'comment.add_comment',
        'comment.add_reply',
        'control.batch_delete_control',
    ]
)
def test_delete_control_delete_related_models(
    graphql_user, graphql_client, graphql_organization, control, users
):
    create_related_models_for_control(users, control.id, graphql_client)

    graphql_client.execute(
        DELETE_CONTROLS,
        variables={
            "input": {
                "ids": [str(control.id)],
                "organizationId": str(graphql_organization.id),
            }
        },
    )

    check_assertions_related_models_were_deleted()


@pytest.mark.functional(
    permissions=[
        'control.can_delete',
        'comment.add_comment',
        'comment.add_reply',
        'control.batch_delete_control',
    ]
)
def test_delete_control_from_admin_delete_related_models(
    graphql_user, graphql_client, graphql_organization, control, users
):
    create_related_models_for_control(users, control.id, graphql_client)

    control_admin_instance = ControlAdmin(Control, AdminSite())
    request = MockRequest()

    control_query_set = Control.objects.filter(id=control.id)

    control_admin_instance.delete_queryset(request, control_query_set)

    check_assertions_related_models_were_deleted()


def create_action_item_and_alert_for_action_item_control(
    graphql_user_email, control_id, graphql_client
):
    input_values = {
        'name': 'RAI-001',
        'description': '',
        'isRequired': True,
        'recurrentSchedule': '',
        'dueDate': '2021-10-13T18:11:34+00:00',
        'owner': graphql_user_email,
        'controlId': control_id,
        'metadata': '{"requiredEvidence": true}',
    }

    graphql_client.execute(ADD_CONTROL_ACTION_ITEM, variables={'input': input_values})


@pytest.mark.functional(permissions=['action_item.add_actionitem'])
def test_delete_control_deletes_related_action_items_alerts(
    graphql_user, graphql_client, graphql_organization, control, users
):
    create_action_item_and_alert_for_action_item_control(
        graphql_user.email, control.id, graphql_client
    )

    control_admin_instance = ControlAdmin(Control, AdminSite())
    request = MockRequest()
    control_query_set = Control.objects.filter(id=control.id)

    control_admin_instance.delete_queryset(request, control_query_set)

    assert Alert.objects.count() == 0
    assert ActionItem.alerts.through.objects.count() == 0
