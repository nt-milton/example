from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0048_update_policies_url'),
    ]

    operations = [
        migrations.RunSQL(
            '''
        BEGIN;
            UPDATE program_subtask
            SET text = REPLACE(
              text,
              'https://app.heylaika.com/integration/gsuite',
              'https://app.heylaika.com/integrations/Google%20Workspace'
            )
            WHERE "group"='policy';
        COMMIT;
        '''
        ),
        migrations.RunSQL(
            '''
        BEGIN;
            UPDATE program_subtask
            SET text = REPLACE(
              text,
              'https://app.heylaika.com/integration',
              'https://app.heylaika.com/integrations?activeTab=standard'
            )
            WHERE "group"='policy';
        COMMIT;
        '''
        ),
    ]
