# Generated by Django 3.2.13 on 2022-07-18 15:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('population', '0020_remove_auditpopulation_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='populationdata',
            name='is_sample',
            field=models.BooleanField(default=False),
        ),
    ]
