from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('auditor', '0002_clean_up_requirement_evidence_relationship_table'),
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
                        WHERE requirement_id IN (
                            SELECT id
                            from public.fieldwork_requirement
                            WHERE is_deleted = true);
           END IF;
        END
        $do$
      '''
        )
    ]
