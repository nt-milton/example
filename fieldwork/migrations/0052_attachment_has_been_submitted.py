# Generated by Django 3.2.12 on 2022-04-25 17:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fieldwork', '0051_add_audit_to_criteria'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='has_been_submitted',
            field=models.BooleanField(default=False),
        ),
    ]
