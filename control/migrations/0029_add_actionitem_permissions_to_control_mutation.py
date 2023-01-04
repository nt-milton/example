# Generated by Django 3.1.12 on 2021-10-14 14:49

from django.db import migrations


def add_default_permissions_for_control_action_item(apps, schema_editor):
    group = apps.get_model('auth', 'Group')
    permission = apps.get_model('auth', 'Permission')

    permissions = permission.objects.filter(
        codename__in=[
            'add_actionitem',
            'change_actionitem',
            'delete_actionitem',
            'view_actionitem',
        ]
    )

    groups = [
        'premium_super',
        'premium_admin',
        'premium_member',
    ]

    for group in group.objects.filter(name__in=groups):
        group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ('control', '0028_add_controlactionitem_permissions_to_premium'),
    ]

    operations = [migrations.RunPython(add_default_permissions_for_control_action_item)]
