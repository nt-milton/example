from django.contrib.auth.management import create_permissions
from django.db import migrations


def create_perms(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0062_add_audit_feedback_table'),
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
                    g.name ilike 'premium_super'
                    OR g.name ilike 'premium_admin'
                    OR g.name ilike 'premium_member'
                )
                AND p.codename = ANY (array [
                    'add_auditfeedback',
                    'change_auditfeedback',
                    'view_auditfeedback',
                    'delete_auditfeedback',
                    'view_auditfeedbackreason'])
                )
            ON CONFLICT DO NOTHING;
            COMMIT;
        '''
        ),
    ]
