# Generated by Django 3.1.12 on 2022-03-24 17:26

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('objects', '0035_organization_object_types_related_name'),
        ('integration', '0051_add_wizard_message_to_denial_of_consent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connectionresponsehistory',
            name='laika_object',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='objects.laikaobject',
            ),
        ),
    ]
