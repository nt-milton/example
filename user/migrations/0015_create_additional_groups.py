# Generated by Django 3.0.7 on 2020-08-25 21:18

from django.db import migrations

from organization.constants import TIERS


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0014_DateTimeField_instead_of_DateField'),
    ]

    def create_viewer_groups(apps, schema):
        Group = apps.get_model('auth', 'Group')
        for tier in TIERS.values():
            Group.objects.create(
                name=f'{tier.lower()}_viewer',
            )

    def add_control_permissions_to_groups(apps, schema):
        Permission = apps.get_model('auth', 'Permission')
        Group = apps.get_model('auth', 'Group')
        groups = Group.objects.filter(name__endswith='_viewer')
        control_permissions = Permission.objects.filter(
            codename__in=[
                'view_policy',
                'view_policytag',
                'view_publishedpolicy',
                'view_training',
            ]
        )
        for g in groups:
            for view_permission in control_permissions:
                g.permissions.add(view_permission)

    operations = [
        migrations.RunPython(create_viewer_groups),
        migrations.RunPython(add_control_permissions_to_groups),
    ]
