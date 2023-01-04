import django.db.models.deletion
from django.db import migrations, models

import monitor.models


class Migration(migrations.Migration):
    dependencies = [
        ('monitor', '0014_monitor_urgency'),
        ('user', '0054_assign_default_watcher_lists'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationmonitor',
            name='watcher_list',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='organization_monitor',
                to='user.watcherlist',
                blank=True,
                null=True,
            ),
        ),
        migrations.RunSQL(
            '''
            BEGIN;
            UPDATE monitor_organizationmonitor AS om
            SET watcher_list_id = wl.id
            FROM user_watcherlist AS wl
            WHERE wl.organization_monitor_id = om.id;
            COMMIT;
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
