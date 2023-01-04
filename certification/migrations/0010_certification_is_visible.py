# Generated by Django 3.1.12 on 2022-01-12 18:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('certification', '0009_adding_certification_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='certification',
            name='is_visible',
            field=models.BooleanField(default=False, verbose_name='Visible in Polaris'),
        ),
    ]
