# Generated by Django 3.0.7 on 2020-07-23 17:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('control', '0010_new_certification_fks'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='controlcertificationsection',
            options={},
        ),
        migrations.AlterField(
            model_name='control',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
