import logging
import re

from django.db import migrations

logger = logging.getLogger(__name__)


def _rename_clubhouse_to_shortcut_vendor_name(apps):
    Vendor = apps.get_model('vendor', 'Vendor')
    clubhouse_vendor_exist = Vendor.objects.filter(name='Clubhouse').exists()
    if clubhouse_vendor_exist:
        clubhouse_vendor = Vendor.objects.get(name='Clubhouse')
        clubhouse_vendor.name = 'Shortcut'
        clubhouse_vendor.save()
        logger.info(f'Vendor Clubhouse renamed to Shortcut.')


def migrate_clubhouse_to_shortcut(apps, schema_editor):
    ConnectionAccount = apps.get_model('integration', 'ConnectionAccount')
    Integration = apps.get_model('integration', 'Integration')

    _rename_clubhouse_to_shortcut_vendor_name(apps)

    shortcut_integration_exist = Integration.objects.filter(
        vendor__name='Shortcut'
    ).exists()
    if shortcut_integration_exist:
        shortcut_integration = Integration.objects.get(vendor__name='Shortcut')
        shortcut_connections = ConnectionAccount.objects.filter(
            integration=shortcut_integration
        )
        logger.info(f'Updating {shortcut_connections.count()} Clubhouse integrations')
        for shortcut_connection in shortcut_connections.all():
            if 'clubhouse' in shortcut_connection.alias.lower():
                new_alias = re.sub(
                    'Clubhouse',
                    'Shortcut',
                    shortcut_connection.alias,
                    flags=re.IGNORECASE,
                )
                shortcut_connection.alias = new_alias
            shortcut_connection.integration = shortcut_integration
            shortcut_connection.save()

            logger.info(
                f'Connection account {shortcut_connection.alias} in '
                f'organization {shortcut_connection.organization} was '
                'updated to Shortcut'
            )


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0032_add_requirements_fields'),
    ]

    operations = [migrations.RunPython(migrate_clubhouse_to_shortcut)]
