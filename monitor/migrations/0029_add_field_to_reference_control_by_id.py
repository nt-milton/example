# Generated by Django 3.1.12 on 2022-01-06 20:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('monitor', '0028_add_user_to_monitor_exclusion_event'),
    ]

    operations = [
        migrations.AddField(
            model_name='monitor',
            name='control_reference_ids',
            field=models.TextField(
                blank=True, default='', verbose_name='Control references by id'
            ),
        ),
    ]
