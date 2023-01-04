from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('population', '0006_update_comment_field'),
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
                     g.name ilike '%_admin' or g.name ilike '%_super'
                  )
                  AND p.codename = ANY (array [
                    'add_auditpopulation',
                    'delete_auditpopulation',
                    'change_auditpopulation',
                    'view_auditpopulation' ]
                    )
                )
            ON CONFLICT DO NOTHING;
            COMMIT;
        '''
        )
    ]
