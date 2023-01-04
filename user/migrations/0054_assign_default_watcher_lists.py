from django.db import connection, migrations

from user.models import DEFAULT_WATCHER_ROLES


class Migration(migrations.Migration):
    dependencies = [('user', '0053_update_user_preferences')]

    operations = [
        migrations.RunSQL(
            '''
        BEGIN;
        SELECT om.id, om.organization_id
        INTO organization_monitors
        FROM monitor_organizationmonitor AS om
        LEFT JOIN user_watcherlist AS wl
        ON wl.organization_monitor_id = om.id
        WHERE
        wl IS NULL;
        INSERT INTO user_watcherlist
        (organization_monitor_id)
        SELECT id FROM organization_monitors;
        INSERT INTO user_watcherlist_users
        (watcherlist_id, user_id)
        SELECT wl.id, u.id
        FROM organization_monitors AS om
        LEFT JOIN user_watcherlist AS wl
        ON wl.organization_monitor_id = om.id
        LEFT JOIN user_user AS u
        ON u.organization_id = om.organization_id
        WHERE u.role IN ('OrganizationAdmin', 'OrganizationMember');
        DROP TABLE organization_monitors;
        COMMIT;
        '''
        )
    ]
