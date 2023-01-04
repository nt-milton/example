from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('auditor', '0001_add_requirement_permission_auditors'),
    ]

    operations = [
        migrations.RunSQL(
            '''
        DO
        $do$
        BEGIN
        IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE 
            TABLE_SCHEMA = 'public' AND  TABLE_NAME = 'fieldwork_requirementevidence') then 
                DELETE FROM public.fieldwork_requirementevidence
                    WHERE evidence_id IN (
                        SELECT id
                        from public.fieldwork_evidence
                        WHERE is_deleted = true);
        END IF;
        END
        $do$
      '''
        )
    ]
