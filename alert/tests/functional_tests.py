import io
from unittest.mock import patch

import pytest
from django.core.files import File

from access_review.mutations import create_access_review_alerts
from access_review.tests.factory import create_access_review
from alert.constants import ALERT_EMAIL_TEMPLATES, ALERT_TYPES, ALERT_TYPES_AUDITOR
from alert.models import Alert, PeopleDiscoveryAlert
from alert.tasks import get_task_and_content_by_alert_type
from alert.tests import (
    GET_AUDITOR_ALERTS,
    GET_CONTROL_NUMBER_NEW_ALERTS,
    GET_NUMBER_NEW_ALERTS,
)
from alert.tests.factory import (
    create_completed_audit,
    create_evidence,
    create_evidence_comment,
)
from alert.tests.mutations import UPDATE_AUDITOR_ALERT, UPDATE_CONTROL_ALERT_VIEWED
from alert.tests.queries import GET_ALERTS
from alert.tests.test_utils import create_alert
from alert.utils import (
    get_requirement_from_alert,
    send_comment_control_alert_email,
    send_comment_policy_alert_email,
)
from audit.constants import AUDIT_FIRMS
from audit.models import AuditAlert, AuditStatus
from audit.tests.factory import associate_organization_audit_firm, create_audit_firm
from comment.models import Comment, CommentAlert, Mention, Reply
from control.models import Control, ControlComment
from fieldwork.models import EvidenceComment, RequirementComment
from library.models import LibraryEntrySuggestionsAlert
from objects.tests.factory import create_lo_with_connection_account
from objects.utils import create_background_check_alerts
from policy.models import Policy, PolicyComment
from policy.tests.factory import create_empty_policy
from program.models import SubTask, SubtaskAlert, TaskComment
from program.tests import create_program, create_task
from training.models import Training, TrainingAlert
from user.constants import ALERT_PREFERENCES, ROLE_SUPER_ADMIN, USER_ROLES
from user.models import User
from user.tests import create_user
from vendor.models import VendorDiscoveryAlert

COMMENT_CONTENT = 'This is a test comment'
COMMENT_CONTENT_2 = 'This is a test comment for same task'
FILE_NAME = 'File_Name.txt'


@pytest.fixture
def create_policy_and_comment(graphql_user, graphql_organization):
    comment_content = 'My comment'

    comment = Comment.objects.create(owner=graphql_user, content=comment_content)

    policy = create_empty_policy(
        organization=graphql_organization, user=graphql_user, name='Policy test'
    )

    PolicyComment.objects.create(policy=policy, comment=comment)

    return comment, policy


@pytest.fixture
def admin_user(graphql_organization):
    return create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='john',
    )


@pytest.fixture
def comments(sender):
    comment = Comment.objects.create(owner=sender, content=COMMENT_CONTENT)

    comment_2 = Comment.objects.create(owner=sender, content=COMMENT_CONTENT_2)

    return comment, comment_2


@pytest.fixture
def sender(graphql_organization):
    return User.objects.create(
        first_name='John',
        last_name='Doe',
        organization=graphql_organization,
        email='sender@heylaika.com',
    )


@pytest.fixture
def alert(graphql_organization, graphql_audit_user):
    sender = create_user(graphql_organization, [], 'sender@mail.com')
    return Alert.objects.create(
        sender=sender, receiver=graphql_audit_user, type='MENTION'
    )


@pytest.fixture
def audit_alert_request(graphql_organization, graphql_audit_user):
    sender = create_user(graphql_organization, [], 'sender@mail.com')
    return Alert.objects.create(
        sender=sender,
        receiver=graphql_audit_user,
        type=ALERT_TYPES_AUDITOR['ORG_REQUESTED_AUDIT'],
    )


@pytest.fixture
def control_comment_alert(graphql_organization, graphql_user):
    sender = create_user(graphql_organization, [], 'sender@mail.com')
    return Alert.objects.create(
        sender=sender, receiver=graphql_user, type=ALERT_TYPES['CONTROL_MENTION']
    )


@pytest.fixture
def program(graphql_organization):
    return create_program(
        organization=graphql_organization,
        name='Privacy Program',
        description='This is an example of program',
    )


@pytest.fixture
def task(graphql_organization, program):
    return create_task(graphql_organization, program)


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
def audit_firm():
    return create_audit_firm(AUDIT_FIRMS[1])


@pytest.fixture
def organization_audit_firm(graphql_organization, audit_firm):
    return associate_organization_audit_firm(graphql_organization, audit_firm)


@pytest.fixture
def audit(graphql_organization, audit_firm):
    return create_completed_audit(graphql_organization, audit_firm)


@pytest.fixture
def evidence(audit):
    return create_evidence(audit)


@pytest.fixture
def evidence_comment(evidence, admin_user, sender, graphql_user):
    return create_evidence_comment(admin_user, evidence, [graphql_user.email])


@pytest.fixture
def evidence_comment_graphql_user(
    evidence,
    graphql_user,
):
    return EvidenceComment.objects.custom_create(
        owner=graphql_user,
        evidence_id=evidence.id,
        tagged_users=[],
        content='Graphql user comment',
        is_internal_comment=True,
    )


@pytest.fixture
def file():
    return File(name=FILE_NAME, file=io.BytesIO('This is a test'.encode()))


@pytest.mark.functional()
def test_resolve_alerts(
    graphql_client,
    admin_user,
    graphql_organization,
    task,
    sender,
    subtask,
    comments,
    audit,
):
    alerts = []
    for comment in comments:
        TaskComment.objects.create(task=task, comment=comment)
        Mention.objects.create(user=admin_user, comment=comment)

        alert = Alert.objects.create(
            sender=sender, receiver=admin_user, type=ALERT_TYPES.get('MENTION')
        )

        SubtaskAlert.objects.create(alert=alert, subtask=subtask)

        CommentAlert.objects.create(alert=alert, comment=comment)

        audit_status = AuditStatus.objects.create(audit=audit, requested=True)

        audit_status.initiated = True
        audit_status.save()

        alert = get_task_and_content_by_alert_type(alert)

        alerts.append(alert)

    assert alerts[0]['message_owner'] == 'John Doe'
    assert alerts[1]['message_owner'] == 'John Doe'
    assert alerts[0]['message_content'] == COMMENT_CONTENT
    assert alerts[1]['message_content'] == COMMENT_CONTENT_2


@pytest.mark.functional
@patch('alert.utils.send_alert_email')
def test_send_comment_policy_alert_email_user_preferences_immediately(
    send_alert_email, graphql_user, graphql_organization, admin_user
):
    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    admin_user.user_preferences['profile']['alerts'] = ALERT_PREFERENCES['IMMEDIATELY']
    admin_user.save()

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    PolicyComment.objects.create(comment=comment, policy=policy)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['POLICY_REPLY']
    )

    alert.send_comment_policy_alert_email(
        policy_message_data={
            'policy': policy,
            'message_content': COMMENT_CONTENT,
            'message_owner': graphql_user,
        },
        hostname='https://other.com',
    )

    assert send_alert_email.delay.call_count == 1
    send_alert_email.delay.assert_called_with(
        {
            'to': 'test@heylaika.com',
            'subject': 'John replied to your comment in Policy.',
            'template_context': {
                'alerts': [
                    {
                        'sender_name': 'John',
                        'message_owner': graphql_user,
                        'alert_action': 'replied to a comment:',
                        'created_at': alert.created_at.isoformat(),
                        'content': 'This is a test comment',
                        'entity_name': 'Policy',
                        'page_section': 'Policies',
                    }
                ],
                'call_to_action_url': f'https://other.com/policies/{policy.id}',
            },
        },
        ALERT_EMAIL_TEMPLATES['COMMENTS'],
    )


@pytest.mark.functional
@patch('alert.utils.send_alert_email')
def test_send_comment_policy_alert_email_user_preferences_never(
    send_alert_email, graphql_user, graphql_organization, admin_user
):
    admin_user.user_preferences['profile']['alerts'] = ALERT_PREFERENCES['NEVER']
    admin_user.save()

    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    PolicyComment.objects.create(comment=comment, policy=policy)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['POLICY_REPLY']
    )

    alert.send_comment_policy_alert_email(
        policy_message_data={
            'policy': policy,
            'message_content': COMMENT_CONTENT,
            'message_owner': graphql_user,
        },
        hostname='https://other.com',
    )

    assert send_alert_email.delay.call_count == 0


@pytest.mark.functional
@patch('alert.utils.send_alert_email')
def test_send_comment_control_alert_email(
    send_alert_email, graphql_user, graphql_organization, admin_user
):
    control = Control.objects.create(organization=graphql_organization, name='Control')

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    ControlComment.objects.create(comment=comment, control=control)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['CONTROL_REPLY']
    )

    send_comment_control_alert_email(
        alert=alert,
        control_related={
            'control': control,
            'message_content': COMMENT_CONTENT,
            'message_owner': graphql_user,
        },
        hostname='https://other.com',
    )

    assert send_alert_email.delay.call_count == 1
    send_alert_email.delay.assert_called_with(
        {
            'to': 'test@heylaika.com',
            'subject': 'John replied to your comment in Control.',
            'template_context': {
                'alerts': [
                    {
                        'sender_name': 'John',
                        'message_owner': graphql_user,
                        'alert_action': 'replied to a comment:',
                        'created_at': alert.created_at.isoformat(),
                        'content': 'This is a test comment',
                        'entity_name': 'Control',
                        'page_section': 'Control',
                    }
                ],
                'call_to_action_url': f'https://other.com/controls/{control.id}',
            },
        },
        ALERT_EMAIL_TEMPLATES['COMMENTS'],
    )


@pytest.mark.functional
@patch('alert.utils.send_alert_email')
def test_send_comment_policy_alert_email(
    send_alert_email, graphql_user, graphql_organization, admin_user
):
    policy = Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    PolicyComment.objects.create(comment=comment, policy=policy)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['POLICY_REPLY']
    )

    send_comment_policy_alert_email(
        alert=alert,
        policy_message_data={
            'policy': policy,
            'message_content': COMMENT_CONTENT,
            'message_owner': graphql_user,
        },
        hostname='https://other.com',
    )

    assert send_alert_email.delay.call_count == 1
    send_alert_email.delay.assert_called_with(
        {
            'to': 'test@heylaika.com',
            'subject': 'John replied to your comment in Policy.',
            'template_context': {
                'alerts': [
                    {
                        'sender_name': 'John',
                        'message_owner': graphql_user,
                        'alert_action': 'replied to a comment:',
                        'created_at': alert.created_at.isoformat(),
                        'content': 'This is a test comment',
                        'entity_name': 'Policy',
                        'page_section': 'Policies',
                    }
                ],
                'call_to_action_url': f'https://other.com/policies/{policy.id}',
            },
        },
        ALERT_EMAIL_TEMPLATES['COMMENTS'],
    )


@pytest.mark.functional
def test_get_requirement_from_alert_required_mention(
    graphql_user, graphql_organization, admin_user, requirement
):
    control = Control.objects.create(organization=graphql_organization, name='Control')

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    RequirementComment.objects.create(requirement=requirement, comment=comment)

    ControlComment.objects.create(comment=comment, control=control)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['REQUIREMENT_MENTION']
    )

    CommentAlert.objects.create(alert=alert, comment=comment)

    result = get_requirement_from_alert(alert=alert)

    assert result.display_id == 'LCL-1'
    assert result.audit.audit_type == 'SOC 2 Type 1'


@pytest.mark.functional
def test_get_requirement_from_alert_required_mention_no_requirement(
    graphql_user, graphql_organization, admin_user
):
    control = Control.objects.create(organization=graphql_organization, name='Control')

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    ControlComment.objects.create(comment=comment, control=control)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['REQUIREMENT_MENTION']
    )

    CommentAlert.objects.create(alert=alert, comment=comment)

    result = get_requirement_from_alert(alert=alert)

    assert result is None


@pytest.mark.functional
def test_get_requirement_from_alert_required_reply(
    graphql_user, graphql_organization, admin_user, requirement
):
    control = Control.objects.create(organization=graphql_organization, name='Control')

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    RequirementComment.objects.create(requirement=requirement, comment=comment)

    ControlComment.objects.create(comment=comment, control=control)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['REQUIREMENT_REPLY']
    )

    result = get_requirement_from_alert(alert=alert)

    assert result.display_id == 'LCL-1'
    assert result.audit.audit_type == 'SOC 2 Type 1'


@pytest.mark.functional
def test_get_requirement_from_alert_required_reply_no_requirement(
    graphql_user, graphql_organization, admin_user
):
    control = Control.objects.create(organization=graphql_organization, name='Control')

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    ControlComment.objects.create(comment=comment, control=control)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['REQUIREMENT_REPLY']
    )

    result = get_requirement_from_alert(alert=alert)

    assert result is None


@pytest.mark.functional
def test_get_requirement_from_alert_not_valid_required(
    graphql_user, graphql_organization, admin_user, requirement
):
    control = Control.objects.create(organization=graphql_organization, name='Control')

    comment = Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)

    RequirementComment.objects.create(requirement=requirement, comment=comment)

    ControlComment.objects.create(comment=comment, control=control)

    reply = Reply.objects.create(owner=admin_user, parent=comment, content='Reply test')

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['CONTROL_REPLY']
    )

    result = get_requirement_from_alert(alert=alert)

    assert result is None


@pytest.mark.functional
def test_send_evidence_alert_email(
    evidence_comment, evidence_comment_graphql_user, sender, admin_user, graphql_user
):
    reply = Reply.objects.create(
        owner=admin_user, parent=evidence_comment_graphql_user, content='Reply test'
    )

    alert = reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['EVIDENCE_REPLY']
    )

    send_email_result = alert.send_evidence_comment_alert_email(
        evidence=evidence_comment.evidence.first(), content=reply.content
    )
    assert send_email_result is not None


@pytest.mark.functional(
    permissions=['fieldwork.add_evidencecomment', 'alert.view_alert']
)
def test_resolve_evidence_alerts(
    graphql_client,
    evidence_comment,
    evidence_comment_graphql_user,
    sender,
    admin_user,
    graphql_user,
):
    graphql_user.role = USER_ROLES['SUPER_ADMIN']
    graphql_user.save()

    reply = Reply.objects.create(
        owner=admin_user, parent=evidence_comment_graphql_user, content='Reply test'
    )
    reply.create_reply_alert(
        graphql_user.organization.id, ALERT_TYPES['EVIDENCE_REPLY']
    )

    reply.add_mentions([graphql_user.email])

    response = graphql_client.execute(GET_ALERTS)
    assert response['data']['alerts'] is not None


@pytest.mark.functional(permissions=['audit.view_auditalert'])
def test_resolve_auditor_alerts(graphql_audit_client, audit_alert_request, audit):
    AuditAlert.objects.create(alert=audit_alert_request, audit=audit)
    response = graphql_audit_client.execute(GET_AUDITOR_ALERTS)
    assert len(response['data']['auditorAlerts']['alerts']) == 1


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_number_new_alerts(graphql_client, alert):
    response = graphql_client.execute(GET_NUMBER_NEW_ALERTS)
    assert response['data']['numberNewAlerts'] == 1


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_control_number_new_alerts(graphql_client, control_comment_alert):
    response = graphql_client.execute(GET_CONTROL_NUMBER_NEW_ALERTS)
    assert response['data']['controlNumberNewAlerts'] == 1


@pytest.mark.functional(permissions=['audit.change_auditalert'])
def test_update_auditor_alerts(graphql_audit_client, alert):
    response = graphql_audit_client.execute(UPDATE_AUDITOR_ALERT)
    assert response['data']['updateAuditorAlertViewed']['success'] is True


@pytest.mark.functional(permissions=['alert.change_alert'])
def test_update_control_alerts(graphql_client, control_comment_alert):
    response = graphql_client.execute(UPDATE_CONTROL_ALERT_VIEWED)
    assert response['data']['updateControlAlertViewed']['success'] is True


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_vendor_alert(
    admin_user, graphql_organization, graphql_user, graphql_client
):
    graphql_user.role = USER_ROLES['SUPER_ADMIN']
    graphql_user.save()
    quantity = 4
    alert = Alert.objects.create(
        sender=None, receiver=graphql_user, type=ALERT_TYPES.get('VENDOR_DISCOVERY')
    )
    VendorDiscoveryAlert.objects.create(alert=alert, quantity=quantity)
    response = graphql_client.execute(GET_ALERTS)
    assert response['data']['alerts']['data'][0]['quantity'] == quantity


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_people_discovery_alert(
    graphql_organization, graphql_client, graphql_user
):
    graphql_user.role = USER_ROLES['SUPER_ADMIN']
    graphql_user.save()
    quantity = 1
    alert = Alert.objects.create(
        sender=None, receiver=graphql_user, type=ALERT_TYPES.get('PEOPLE_DISCOVERY')
    )
    PeopleDiscoveryAlert.objects.create(alert=alert, quantity=quantity)
    response = graphql_client.execute(GET_ALERTS)
    assert response['data']['alerts']['data'][0]['quantity'] == quantity


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_training_alert(
    admin_user, graphql_organization, file, graphql_user, graphql_client
):
    graphql_user.role = USER_ROLES['SUPER_ADMIN']
    graphql_user.save()
    alert = Alert.objects.create(
        sender=None, receiver=graphql_user, type=ALERT_TYPES.get('TRAINING_REMINDER')
    )
    training = Training.objects.create(
        organization=graphql_organization,
        name='Test Name',
        category='Asset Management',
        description='Test Description',
        slides=file,
    )
    TrainingAlert.objects.create(alert=alert, training=training)
    response = graphql_client.execute(GET_ALERTS)
    assert (
        response['data']['alerts']['data'][0]['receiverName'] == graphql_user.first_name
    )


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_lo_background_check_alert(
    graphql_organization, graphql_client, graphql_user
):
    graphql_user.role = USER_ROLES['ADMIN']
    graphql_user.save()
    first_name = 'leo'
    last_name = 'messi'
    laika_object, _ = create_lo_with_connection_account(
        graphql_organization,
        data={'Id': 1, 'First Name': first_name, 'Last Name': last_name},
    )
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
    create_background_check_alerts(
        alert_related_object={'laika_object': laika_object},
        alert_related_model='objects.LaikaObjectAlert',
        alert_type=alert_type,
        organization_id=graphql_organization.id,
    )
    response = graphql_client.execute(GET_ALERTS)
    alert = response['data']['alerts']['data'][0]
    assert alert.get('url') == f'lob/background_check?object={1}'
    assert alert.get('type') == alert_type
    assert alert.get('actionItemDescription') == f'{first_name} {last_name}'


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_lo_background_check_alert_with_no_lo(
    graphql_organization, graphql_client, graphql_user
):
    graphql_user.role = USER_ROLES['ADMIN']
    graphql_user.save()
    first_name = 'leo'
    last_name = 'messi'
    laika_object, _ = create_lo_with_connection_account(
        graphql_organization,
        data={'Id': 1, 'First Name': first_name, 'Last Name': last_name},
    )
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
    create_background_check_alerts(
        alert_related_object={'laika_object': laika_object},
        alert_related_model='objects.LaikaObjectAlert',
        alert_type=alert_type,
        organization_id=graphql_organization.id,
    )
    laika_object.delete()
    response = graphql_client.execute(GET_ALERTS)
    alert = response['data']['alerts']['data'][0]
    assert alert.get('url') == 'not-found'
    assert alert.get('type') == alert_type
    assert alert.get('actionItemDescription') == 'A record'


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_user_alert(graphql_organization, graphql_client, graphql_user):
    graphql_user.role = USER_ROLES['ADMIN']
    graphql_user.save()
    first_name = graphql_user.first_name
    last_name = graphql_user.last_name
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO')
    create_background_check_alerts(
        alert_related_object={'user': graphql_user},
        alert_related_model='user.UserAlert',
        alert_type=alert_type,
        organization_id=graphql_organization.id,
    )
    response = graphql_client.execute(GET_ALERTS)
    alert = response['data']['alerts']['data'][0]
    assert alert.get('url') == f'people?userId={graphql_user.id}'
    assert alert.get('type') == alert_type
    assert alert.get('actionItemDescription') == f'{first_name} {last_name}'


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_alerts_policy(
    graphql_organization, graphql_client, graphql_user, create_policy_and_comment
):
    comment, policy = create_policy_and_comment

    alert = create_alert(user=graphql_user, type=ALERT_TYPES.get('POLICY_MENTION'))

    CommentAlert.objects.create(alert=alert, comment=comment)

    alert_type = ALERT_TYPES.get('POLICY_MENTION')

    response = graphql_client.execute(GET_ALERTS)
    alert = response['data']['alerts']['data'][0]
    assert alert.get('url') == f'policies/{policy.id}'
    assert alert.get('type') == alert_type
    assert alert.get('policyName') == 'Policy test'


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_user_alert_with_no_user(
    graphql_organization, graphql_client, graphql_user
):
    graphql_user.role = USER_ROLES['ADMIN']
    graphql_user.save()
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO')
    create_background_check_alerts(
        alert_type=alert_type, organization_id=graphql_organization.id
    )
    response = graphql_client.execute(GET_ALERTS)
    alert = response['data']['alerts']['data'][0]
    assert alert.get('url') == 'not-found'
    assert alert.get('type') == alert_type
    assert alert.get('actionItemDescription') == 'a user'


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_alert_for_access_review(
    graphql_organization, graphql_client, graphql_user
):
    graphql_user.role = USER_ROLES['ADMIN']
    graphql_user.save()
    access_review = create_access_review(graphql_organization, None)
    create_access_review_alerts(
        graphql_organization.id,
        [graphql_user],
        ALERT_TYPES['ACCESS_REVIEW_START'],
        graphql_user,
        graphql_user.first_name,
        access_review,
    )

    response = graphql_client.execute(GET_ALERTS)
    alert = response['data']['alerts']['data'][0]
    assert alert.get('url') == 'not-found'
    assert alert.get('type') == ALERT_TYPES['ACCESS_REVIEW_START']
    assert alert.get('accessReviewName') == access_review.name


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_resolve_library_entry_suggestion_alert(
    graphql_organization, graphql_client, graphql_user
):
    suggestions_quantity = 1
    alert_type = ALERT_TYPES.get('LIBRARY_ENTRY_SUGGESTIONS')
    suggestion_alert = LibraryEntrySuggestionsAlert.objects.custom_create(
        quantity=suggestions_quantity,
        organization=graphql_organization,
        sender=graphql_user,
        receiver=graphql_user,
        alert_type=alert_type,
    )
    response = graphql_client.execute(GET_ALERTS)
    alert = response['data']['alerts']['data'][0]
    assert alert.get('id') == str(suggestion_alert.id)
    assert alert.get('type') == alert_type
    assert alert.get('quantity') == suggestions_quantity
