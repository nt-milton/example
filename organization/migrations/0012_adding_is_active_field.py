# Generated by Django 3.1.2 on 2021-02-15 22:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0011_setting_permissions_to_roles'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
