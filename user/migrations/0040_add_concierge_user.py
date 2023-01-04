# Generated by Django 3.1.6 on 2021-04-30 16:02

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0039_add_auditor_help_text'),
    ]

    operations = [
        migrations.CreateModel(
            name='Concierge',
            fields=[
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name='concierge',
                        serialize=False,
                        to='user.user',
                    ),
                ),
            ],
        ),
    ]
