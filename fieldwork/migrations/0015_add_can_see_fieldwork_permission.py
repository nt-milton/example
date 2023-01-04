# Generated by Django 3.1.6 on 2021-07-13 12:25

from django.db import migrations


def create_permission(apps, model, codename, name):
    content_type = apps.get_model('contenttypes', 'ContentType')
    permission = apps.get_model('auth', 'Permission')
    obj_content_type = content_type.objects.get_for_model(model)
    content_type = content_type.objects.get(
        app_label=obj_content_type.app_label, model=obj_content_type.model
    )
    permission.objects.get_or_create(
        codename=codename, name=name, content_type=content_type
    )


permissions = [
    ('view_fieldwork', 'Can see fieldwork'),
]


def create_fieldwork_permissions(apps, schema_editor):
    fieldwork_model = apps.get_model('fieldwork', 'Evidence')

    for p in permissions:
        create_permission(apps, fieldwork_model, p[0], p[1])


class Migration(migrations.Migration):
    dependencies = [
        ('fieldwork', '0014_rename_er_display_id'),
        ('user', '0048_remove_can_see_fieldwork_permissions'),
    ]

    operations = [
        migrations.RunPython(create_fieldwork_permissions),
        migrations.RunSQL(
            '''
                BEGIN;
                INSERT into
                   public.auth_group_permissions (group_id, permission_id) (
                   SELECT
                      g.id AS group_id, p.id AS permission_id 
                   FROM
                      public.auth_group g 
                      cross join
                         public.auth_permission p 
                      join django_content_type ct on ct.id = p.content_type_id 
                   WHERE g.name ilike '%_super%'
                      AND p.codename = 'view_fieldwork'
                        AND ct.app_label = 'fieldwork' AND ct.model ='evidence'
                    )
                ON CONFLICT DO NOTHING;
                COMMIT;
            '''
        ),
    ]
