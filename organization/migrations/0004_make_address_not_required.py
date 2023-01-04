# Generated by Django 3.0.2 on 2020-02-17 20:13

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('address', '0001_squashed-address'),
        ('organization', '0003_auto_20200210_1720'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='billing_address',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='billing_address',
                to='address.Address',
            ),
        ),
        migrations.AlterField(
            model_name='organization',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4, primary_key=True, serialize=False
            ),
        ),
    ]
