from django.db import migrations


def add_default_permissions_for_apofpr(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    archived_permissions = Permission.objects.filter(
        codename__in=[
            'view_archivedsubtask',
            'view_archivedtask',
            'view_archivedevidence',
            'delete_archivedprogram',
            'view_archivedprogram',
            'view_archiveduser',
        ]
    )
    groups = [
        'premium_super',
        'premium_admin',
        'premium_member',
    ]
    for group in Group.objects.filter(name__in=groups):
        for permission in archived_permissions:
            group.permissions.add(permission)

    archived_permissions = Permission.objects.filter(
        codename__in=[
            'add_archivedsubtask',
            'change_archivedsubtask',
            'delete_archivedsubtask',
            'add_archivedtask',
            'change_archivedtask',
            'delete_archivedtask',
            'add_archivedevidence',
            'change_archivedevidence',
            'delete_archivedevidence',
            'add_archiveduser',
            'change_archiveduser',
            'delete_archiveduser',
            'add_archivedprogram',
            'change_archivedprogram',
        ]
    )

    premium_super = Group.objects.get(name='premium_super')
    for permission in archived_permissions:
        premium_super.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0031_create_archived_user_model'),
    ]

    operations = [migrations.RunPython(add_default_permissions_for_apofpr)]
