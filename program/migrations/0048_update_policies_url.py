from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0047_create_action_item_related_model_on_subtask'),
    ]

    operations = [
        migrations.RunSQL(
            '''
        BEGIN;
            UPDATE program_subtask
            SET text = REPLACE(
              text,
              'https://app.heylaika.com/policies-beta',
              'https://app.heylaika.com/policies'
            )
            WHERE "group"='policy';
        COMMIT;
        '''
        )
    ]
