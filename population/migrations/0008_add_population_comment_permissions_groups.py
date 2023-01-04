from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('population', '0007_add_population_permissions_groups'),
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
                    'add_populationcomment',
                    'delete_populationcomment',
                    'change_populationcomment',
                    'view_populationcomment' ]
                    )
                )
            ON CONFLICT DO NOTHING;
            COMMIT;
        '''
        )
    ]
