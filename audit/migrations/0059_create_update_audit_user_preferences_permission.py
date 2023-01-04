from django.db import migrations


def create_permission(apps, schema_editor):
    audit_auditor = apps.get_model('audit', 'AuditAuditor')
    content_type = apps.get_model('contenttypes', 'ContentType')
    permission = apps.get_model('auth', 'Permission')
    obj_content_type = content_type.objects.get_for_model(audit_auditor)
    content_type = content_type.objects.get(
        app_label=obj_content_type.app_label, model=obj_content_type.model
    )
    permission.objects.get_or_create(
        codename='update_audit_user_preferences',
        name='Can update audit user preferences',
        content_type=content_type,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0058_auditfirm_signature_text'),
    ]

    operations = [
        migrations.RunPython(create_permission),
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
                                         g.name = 'auditor_admin' or g.name = 'auditor'
                                      )
                                      AND p.codename = ANY (array ['update_audit_user_preferences'])
                                    )
                                ON CONFLICT DO NOTHING;
                                COMMIT;
                            '''
        ),
    ]
