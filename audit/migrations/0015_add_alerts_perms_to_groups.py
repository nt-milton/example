# Generated by Django 3.1.6 on 2021-05-10 17:54

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0014_add_view_user_permission'),
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
                      'view_auditalert',
                      'change_auditalert'
                      ]
                      )
                  )
              ON CONFLICT DO NOTHING;
              COMMIT;
          '''
        )
    ]
