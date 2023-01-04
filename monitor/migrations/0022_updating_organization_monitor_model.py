# Generated by Django 3.1.12 on 2021-10-27 11:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('monitor', '0021_monitor_subtask_reference'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationmonitor',
            name='name',
            field=models.CharField(default='', max_length=64, blank=True),
        ),
        migrations.AddField(
            model_name='organizationmonitor',
            name='query',
            field=models.TextField(default='', blank=True),
        ),
        migrations.AddField(
            model_name='organizationmonitor',
            name='description',
            field=models.TextField(default='', blank=True),
        ),
    ]
