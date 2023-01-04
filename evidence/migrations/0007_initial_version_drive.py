# Generated by Django 3.0.7 on 2020-08-04 20:08

from django.db import migrations, models

from evidence.models import EVIDENCE_TYPE


class Migration(migrations.Migration):
    dependencies = [
        ('evidence', '0006_remove_other_evidence_column'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evidence',
            name='type',
            field=models.CharField(blank=True, choices=EVIDENCE_TYPE, max_length=20),
        ),
    ]
