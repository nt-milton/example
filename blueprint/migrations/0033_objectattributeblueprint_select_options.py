# Generated by Django 3.2.13 on 2022-05-27 16:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('blueprint', '0032_objectattributeblueprint_default_value'),
    ]

    operations = [
        migrations.AddField(
            model_name='objectattributeblueprint',
            name='select_options',
            field=models.CharField(blank=True, max_length=512),
        ),
    ]
