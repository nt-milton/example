from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from audit.models import AuditFirm
from objects.models import LaikaObject
from objects.system_types import USER, resolve_laika_object_type
from user.admin import Auditor, User
from user.models import DISCOVERY_STATE_CONFIRMED, Team

DEFAULT_USER_PREFERENCES = {'profile': {'alerts': 'Never', 'emails': 'Daily'}}


def create_user(
    organization, permissions=[], email=None, user_preferences=None, **kwargs
) -> User:
    """Build a test user with the expected permissions"""
    if not email:
        email = 'test@heylaika.com'
    if not user_preferences:
        user_preferences = DEFAULT_USER_PREFERENCES
    user = User.objects.create(
        organization=organization,
        email=email,
        user_preferences=user_preferences,
        **kwargs
    )
    for permission in permissions:
        _add_permission(user, permission)
    return user


def create_user_auditor(
    audit_firm='Test Audit Firm',
    permissions=[],
    email=None,
    user_preferences=None,
    username=None,
    with_audit_firm=False,
    **kwargs
):
    if not email:
        email = 'testauditor@heylaika.com'
    if not user_preferences:
        user_preferences = DEFAULT_USER_PREFERENCES
    if not username:
        username = 'testauditor@heylaika.com'

    user = User.objects.create(
        email=email, user_preferences=user_preferences, username=username, **kwargs
    )
    for permission in permissions:
        _add_permission(user, permission)

    auditor = Auditor(user=user)
    auditor.save(is_not_django=True)
    if with_audit_firm:
        firm, _ = AuditFirm.objects.get_or_create(name=audit_firm)
        auditor.audit_firms.set([firm])
    return auditor


def create_candidate_user(
    organization,
    email=None,
    user_preferences=None,
    discovery_state=DISCOVERY_STATE_CONFIRMED,
    **kwargs
):
    if not email:
        email = 'test@heylaika.com'
    if not user_preferences:
        user_preferences = DEFAULT_USER_PREFERENCES
    user = User.objects.create(
        organization=organization,
        email=email,
        user_preferences=user_preferences,
        discovery_state=discovery_state,
        **kwargs
    )
    return user


def _add_permission(user, permission):
    model, codename = permission.split('.')
    permission_model = Permission.objects.filter(
        codename=codename, content_type__app_label=model
    ).first()

    #   This is for custom permissions that are created via migrations
    if not permission_model:
        content_type, _ = ContentType.objects.get_or_create(
            app_label=model, model=model
        )
        permission_model = Permission.objects.create(
            codename=codename,
            name=codename,
            content_type=content_type,
        )

    user.user_permissions.add(permission_model)


def create_team(organization, name=None, description='', charter='', notes=''):
    if not name:
        name = 'Team Test'
    return Team.objects.create(
        organization=organization,
        name=name,
        description=description,
        charter=charter,
        notes=notes,
    )


def create_lo_user(organization, email, source_system='test', id='99999'):
    lo_type = resolve_laika_object_type(organization, USER)
    user_data = {
        'Id': id,
        'First Name': 'John',
        'Last Name': 'Doe',
        'Email': email,
        'Is Admin': False,
        'Title': 'Title Updated',
        'Roles': '',
        'Organization Name': 'Organization',
        'Mfa Enabled': True,
        'Mfa Enforced': True,
        'Source System': source_system,
        'Connection Name': 'Connection Name Updated',
        'Groups': 'Groups Updated',
    }
    lo_user = LaikaObject.objects.create(object_type=lo_type, data=user_data)
    return lo_user
