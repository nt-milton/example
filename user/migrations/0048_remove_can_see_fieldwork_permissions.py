# Generated by Django 3.1.6 on 2021-07-12 13:04

from django.db import migrations


def remove_permission(apps, codename, name):
    permission_model = apps.get_model('auth', 'Permission')
    permission = permission_model.objects.filter(codename=codename, name=name)
    permission.delete()


permissions = [
    ('view_fieldwork', 'Can see fieldwork'),
]


def remove_user_permissions(apps, schema_editor):
    for p in permissions:
        remove_permission(apps, p[0], p[1])


class Migration(migrations.Migration):
    dependencies = [('user', '0047_add_can_see_fieldwork_permissions')]

    operations = [
        migrations.RunSQL(
            '''
                BEGIN;
                DELETE FROM public.auth_group_permissions
                WHERE id IN (
                    SELECT id FROM
                    public.auth_group_permissions a 
                    INNER JOIN (
                        SELECT
                            g.id AS group_id, p.id AS permission_id 
                        FROM public.auth_group g 
                        CROSS JOIN
                            public.auth_permission p 
                        JOIN django_content_type ct 
                        ON ct.id = p.content_type_id 
                        WHERE g.name ilike '%_super%'
                        AND p.codename = 'view_fieldwork'
                        AND ct.app_label = 'user' AND ct.model = 'user'
                    ) b
                    ON a.group_id = b.group_id 
                    AND a.permission_id = b.permission_id
                );
                COMMIT;
            '''
        ),
        migrations.RunPython(remove_user_permissions),
    ]
