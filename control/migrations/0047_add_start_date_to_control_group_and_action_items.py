# Generated by Django 3.2.15 on 2022-10-05 14:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('control', '0046_delete_implementationguide'),
    ]

    operations = [
        migrations.AddField(
            model_name='controlgroup',
            name='start_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
