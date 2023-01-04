# Generated by Django 3.1.6 on 2021-07-06 23:12

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('fieldwork', '0012_attachment_is_deleted'),
    ]

    operations = [
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
               WHERE
                  (
                     g.name ilike '%_admin' 
                     OR g.name ilike '%_super'
                     OR g.name ilike '%auditor'
                  )
                  AND p.codename = ANY (array [
                    'add_evidencecomment',
                    'delete_evidencecomment',
                    'change_evidencecomment',
                    'view_evidencecomment' ]
                    )
                )
            ON CONFLICT DO NOTHING;
            COMMIT;
        '''
        )
    ]
