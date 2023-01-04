from django.db import migrations


def add_permission_to_superadmin_group(apps, schema_editor):
    group = apps.get_model('auth', 'Group')
    permission = apps.get_model('auth', 'Permission')
    g = group.objects.get(name='premium_admin')
    permissions_for_sso = [
        'add_identityprovider',
        'view_identityprovider',
        'change_identityprovider',
        'delete_identityprovider',
    ]
    permissions = permission.objects.filter(codename__in=permissions_for_sso)
    g.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ('sso', '0009_sso_change_organization_length'),
    ]

    operations = [migrations.RunPython(add_permission_to_superadmin_group)]
