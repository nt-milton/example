import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0054_assign_default_watcher_lists'),
        ('monitor', '0015_organizationmonitor_watchers'),
        ('organization', '0046_organization_is_internal'),
    ]

    operations = [
        migrations.AddField(
            model_name='watcherlist',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='organization.organization',
                blank=True,
                null=True,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='watcherlist',
            name='name',
            field=models.TextField(blank=True, null=True),
            preserve_default=False,
        ),
        migrations.RunSQL(
            '''
            BEGIN;
            UPDATE user_watcherlist AS wl
            SET organization_id = om.organization_id, name = m.name
            FROM monitor_organizationmonitor AS om
            LEFT JOIN monitor_monitor as m ON om.monitor_id = m.id
            WHERE om.watcher_list_id = wl.id;
            COMMIT;
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='watcherlist',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='organization.organization',
            ),
        ),
        migrations.AlterField(
            model_name='watcherlist',
            name='name',
            field=models.TextField(),
        ),
        migrations.RemoveField(
            model_name='watcherlist',
            name='organization_monitor',
        ),
    ]
