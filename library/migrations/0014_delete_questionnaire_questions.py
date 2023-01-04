from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('library', '0013_question_deleted_at'),
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
                          join django_content_type ct on ct.id = p.content_type_id 
                       WHERE
                          (
                             g.name ilike '%_admin' 
                             OR g.name ilike '%_super' 
                             OR g.name ilike '%_member'
                          )
                          AND p.codename = ANY (array [
                            'add_question',
                            'view_question',
                            'delete_question',
                            'change_question'
                            ]
                            )
                            AND ct.app_label = 'library'
                        )
                    ON CONFLICT DO NOTHING;
                    COMMIT;
                ''',
            reverse_sql='',
        ),
    ]
