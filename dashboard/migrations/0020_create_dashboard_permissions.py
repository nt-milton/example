# Generated by Django 3.1.12 on 2022-01-07 17:44

from django.contrib.auth.management import create_permissions
from django.db import migrations


def allow_dashboard_actions_for_premium_admin_contributor(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    permissions = Permission.objects.filter(
        codename__in=['view_certification_readiness', 'view_quick_links']
    )

    groups = ['premium_super', 'premium_admin', 'premium_member']

    for group in Group.objects.all():
        group.permissions.remove(*permissions)

    for group in Group.objects.filter(name__in=groups):
        for permission in permissions:
            group.permissions.add(permission)


def create_perms(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


class Migration(migrations.Migration):
    dependencies = [
        ('dashboard', '0019_add_policy_dashboard_view'),
        ('certification', '0009_adding_certification_permissions'),
        ('organization', '0067_adding_quick_links_permissions'),
    ]

    operations = [
        migrations.RunPython(create_perms, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(
            allow_dashboard_actions_for_premium_admin_contributor,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
