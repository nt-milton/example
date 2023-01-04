import unittest

import pytest

from alert.tasks import send_digest_alert_email
from audit.constants import AUDIT_FIRMS
from audit.models import AuditStatus
from audit.tests.factory import create_audit_firm
from dashboard.tests.factory import create_subtask
from organization.tests.factory import create_organization
from program.tests import create_task
from user.constants import ROLE_SUPER_ADMIN
from user.tests import create_user

from .factory import create_comment, create_completed_audit, create_reply


@pytest.fixture
def organization():
    return create_organization(name='Laika Dev')


@pytest.fixture
def admin_user(organization):
    return create_user(
        organization,
        email='jhon@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='john',
    )


@pytest.fixture()
def task(organization):
    return create_task(organization=organization)


@pytest.fixture
def audit_firm():
    return create_audit_firm(AUDIT_FIRMS[0])


@pytest.fixture
def audit(organization, audit_firm):
    return create_completed_audit(organization, audit_firm)


@pytest.mark.functional
def test_send_digest_alert_email(organization, task, audit, admin_user):
    case = unittest.TestCase()
    user1 = create_user(
        organization,
        email='john@superadmin.com',
    )

    result = send_digest_alert_email.delay().get()
    assert result.get('success') is True
    assert result.get('emails_sent') == 0

    user2 = create_user(
        organization,
        email='john2@superadmin.com',
        user_preferences={"profile": {"alerts": "Daily", "emails": "Daily"}},
        role=ROLE_SUPER_ADMIN,
    )
    result = send_digest_alert_email.delay().get()
    assert result.get('success') is True
    assert result.get('emails_sent') == 0
    case.assertCountEqual(result['missed_users'], ['john2@superadmin.com'])

    subtask = create_subtask(user1, task)

    comment = create_comment(
        organization=organization,
        owner=user2,
        content='This is a comment',
        task_id=task.id,
        subtask_id=subtask.id,
    )
    reply = create_reply(owner=user1, comment=comment, content='This is a reply')
    room_id = reply.owner.organization.id
    reply.create_reply_alert(room_id)

    audit_status = AuditStatus.objects.create(audit=audit, requested=True)

    audit_status.initiated = True
    audit_status.save()
    alerts = audit_status.create_audit_stage_alerts()
    for alert in alerts:
        alert.send_audit_alert_email(audit_status)

    result = send_digest_alert_email.delay().get()
    assert result.get('success') is True
    assert result.get('emails_sent') == 2
