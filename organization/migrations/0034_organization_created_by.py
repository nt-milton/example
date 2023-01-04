# Generated by Django 3.1.6 on 2021-05-07 15:28

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('organization', '0033_updating_default_org_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='organization_created_by',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
