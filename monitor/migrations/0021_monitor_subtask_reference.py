# Generated by Django 3.1.12 on 2021-11-02 19:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('monitor', '0020_create_monitor_exclusion_criteria'),
    ]

    operations = [
        migrations.AddField(
            model_name='monitor',
            name='subtask_reference',
            field=models.TextField(
                blank=True, null=True, verbose_name='Subtask reference'
            ),
        ),
    ]
