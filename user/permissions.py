import logging

from django.contrib.auth.models import Group

from audit.constants import AUDITOR_ROLES
from laika.settings import DJANGO_SETTINGS
from user.constants import USER_GROUPS, USER_ROLES

DJANGO_ADMIN = DJANGO_SETTINGS.get('DJANGO_SUPERUSER_EMAIL')
logger = logging.getLogger('user_permissions')

ORGANIZATION = 'Organization'


def get_permissions_group(role):
    if role is None:
        raise ValueError
    return Group.objects.get(name=USER_GROUPS.get(role) or '')


def add_user_to_group(user):
    if user.email == DJANGO_ADMIN:
        return

    user.groups.add(get_permissions_group(user.role))


def add_audit_user_to_group(user):
    if user.email == DJANGO_ADMIN:
        return

    group = Group.objects.get(name='auditor')
    if user.role == AUDITOR_ROLES['auditorAdmin']:
        group = Group.objects.get(name='auditor_admin')

    user.groups.add(group)


def add_concierge_user_to_group(user):
    if user.email == DJANGO_ADMIN:
        return

    group = Group.objects.get(name='concierge')
    user.groups.add(group)


def is_organization_admin(user):
    return user.role == USER_ROLES['ADMIN']


def change_user_permissions_group(old_role, new_role, user):
    old_group = get_permissions_group(old_role)
    new_group = get_permissions_group(new_role)
    user.groups.remove(old_group)
    user.groups.add(new_group)
