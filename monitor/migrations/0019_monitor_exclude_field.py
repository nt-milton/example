# Generated by Django 3.1.12 on 2021-09-28 18:12

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('monitor', '0018_add_fix_me_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='monitor',
            name='exclude_field',
            field=models.TextField(blank=True, default='', null=True),
        ),
    ]
