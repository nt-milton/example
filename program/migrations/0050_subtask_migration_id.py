# Generated by Django 3.2.14 on 2022-07-28 16:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0049_update_subtasks_urls'),
    ]

    operations = [
        migrations.AddField(
            model_name='subtask',
            name='migration_id',
            field=models.CharField(blank=True, default='', max_length=1024),
        ),
    ]
