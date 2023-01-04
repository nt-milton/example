# Generated by Django 3.1.12 on 2021-12-14 20:41

from django.db import migrations


def create_api_admin_group_with_permissions(apps, schema_editor):
    group = apps.get_model('auth', 'Group')
    permission = apps.get_model('auth', 'Permission')
    g = group.objects.create(name='open_api_admin')
    permissions_for_open_api_admin = [
        'view_laikaobjecttype',
        'add_laikaobject',
        'change_laikaobject',
        'delete_laikaobject',
        'view_laikaobject',
        'bulk_upload_object',
    ]
    permissions = permission.objects.filter(codename__in=permissions_for_open_api_admin)
    g.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0064_create_api_token_model'),
    ]

    operations = [migrations.RunPython(create_api_admin_group_with_permissions)]
