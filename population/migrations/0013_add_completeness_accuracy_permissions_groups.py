from django.contrib.auth.management import create_permissions
from django.db import migrations


def create_perms(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


class Migration(migrations.Migration):
    dependencies = [
        ('population', '0012_add_population_completeness_accuracy_table'),
    ]

    operations = [
        migrations.RunPython(create_perms),
        migrations.RunSQL(
            '''
            BEGIN;
            INSERT into
               public.auth_group_permissions (group_id, permission_id)
               (SELECT
                  g.id AS group_id,
                  p.id AS permission_id
                FROM
                  public.auth_group g
                  cross join
                  public.auth_permission p
                WHERE (
                    g.name ilike '%_admin' or g.name ilike '%_super'
                )
                AND p.codename = ANY (array [
                    'add_populationcompletenessaccuracy',
                    'delete_populationcompletenessaccuracy',
                    'change_populationcompletenessaccuracy',
                    'view_populationcompletenessaccuracy' ])
                )
            ON CONFLICT DO NOTHING;
            COMMIT;
        '''
        ),
    ]
