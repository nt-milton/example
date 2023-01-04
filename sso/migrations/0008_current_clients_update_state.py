from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('sso', '00007_add_permission_to_superadmin_group'),
    ]

    operations = [
        migrations.RunSQL(
            '''
        UPDATE sso_identityprovider SET state='DONE_ENABLED'
        WHERE id IN (1,2,3,4,5,7,8,10,11,12,13,14,15,16,17,34,68,69,6)
        '''
        )
    ]
