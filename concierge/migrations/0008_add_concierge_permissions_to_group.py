# Generated by Django 3.1.6 on 2021-04-30 19:14

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('concierge', '0007_add_concierge_group_and_permissions'),
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
                                     g.name = 'concierge'
                                  )
                                  AND p.codename = ANY (array [
                                    'add_concierge',
                                    'change_concierge',
                                    'delete_concierge',
                                    'view_concierge'
                                    ])
                                )
                            ON CONFLICT DO NOTHING;
                            COMMIT;
                        '''
        ),
    ]
