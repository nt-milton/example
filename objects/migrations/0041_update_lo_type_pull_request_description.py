from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('objects', '0040_update_lo_required_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql='''
            BEGIN;
            UPDATE objects_laikaobjecttype 
            SET description = 'A pull request from a source control system. There is an integration available: (<a href="https://app.heylaika.com/integrations/Github%20Apps" target="blank">GitHub Apps</a>)'
            WHERE type_name = 'pull_request' 
            AND description = 'A pull request from a source control system. There is an integration available: (<a href="https://app.heylaika.com/integrations/GitHub" target="blank">GitHub</a>)';
            COMMIT;
            ''',
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
