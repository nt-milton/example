# Generated by Django 3.1.12 on 2021-07-28 20:32

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0048_remove_can_see_fieldwork_permissions'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='user',
            options={'ordering': ['organization', 'first_name']},
        ),
    ]
