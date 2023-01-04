# Generated by Django 3.1.12 on 2021-10-21 20:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fieldwork', '0038_evidence_times_moved_back_to_open'),
    ]

    operations = [
        migrations.AddField(
            model_name='evidencecomment',
            name='pool',
            field=models.CharField(
                choices=[
                    ('lcl', 'LCL'),
                    ('all', 'All'),
                    ('laika', 'Laika'),
                    ('lcl-cx', 'LCL-CX'),
                ],
                max_length=10,
                null=True,
            ),
        ),
    ]
