# Generated by Django 3.1.12 on 2021-09-28 20:38

from django.contrib.auth.models import Group, Permission
from django.db import migrations
from django.db.models import Q


def add_permissions(apps, schema_editor):
    groups = Group.objects.filter(
        Q(name__contains='_admin') | Q(name__contains='_super')
    )
    permissions = Permission.objects.filter(
        codename__in=[
            'add_organizationchecklist',
            'change_organizationchecklist',
            'delete_organizationchecklist',
            'view_organizationchecklist',
            'add_organizationchecklistitem',
            'change_organizationchecklistitem',
            'delete_organizationchecklistitem',
            'view_organizationchecklistitem',
        ]
    )
    for group in groups:
        group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0051_add_checklist'),
    ]

    operations = [
        migrations.RunPython(add_permissions, reverse_code=migrations.RunPython.noop),
    ]
