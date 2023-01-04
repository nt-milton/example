# Generated by Django 3.1.12 on 2021-09-03 05:50

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fieldwork', '0030_add_view_criteria_auditor_permission'),
    ]

    operations = [
        migrations.CreateModel(
            name='Test',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('display_id', models.CharField(max_length=50)),
                ('name', models.TextField()),
                ('checklist', models.TextField()),
                (
                    'result',
                    models.CharField(
                        choices=[
                            ('exceptions_noted', 'Exceptions Noted'),
                            ('no_exceptions_noted', 'No Exceptions Noted'),
                            ('not_tested', 'Not Tested'),
                        ],
                        max_length=100,
                    ),
                ),
                ('notes', models.TextField(blank=True, null=True)),
                (
                    'requirement',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='tests',
                        to='fieldwork.requirement',
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='test',
            constraint=models.CheckConstraint(
                check=models.Q(
                    result__in=['exceptions_noted', 'no_exceptions_noted', 'not_tested']
                ),
                name='fieldwork_test_valid_test_result',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='test',
            unique_together={('display_id', 'requirement')},
        ),
    ]
