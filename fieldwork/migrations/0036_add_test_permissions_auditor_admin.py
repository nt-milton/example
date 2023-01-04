from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('fieldwork', '0035_fix_requirement_comment_auditor_permission'),
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
                        g.name = 'auditor' or g.name = 'auditor_admin'
                      )
                      AND p.codename = ANY (array [
                        'view_test',
                        'change_test',
                        'add_test',
                        'delete_test' ]
                        )
                    )
                ON CONFLICT DO NOTHING;
                COMMIT;
            '''
        )
    ]
