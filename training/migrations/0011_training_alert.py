# Generated by Django 3.1.6 on 2021-04-19 20:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('alert', '0009_add_training_reminder_choice'),
        ('training', '0010_delele_on_cascade_for_alumni_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingAlert',
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
                (
                    'alert',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='training_alert',
                        to='alert.alert',
                    ),
                ),
                (
                    'training',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='alerts',
                        to='training.training',
                    ),
                ),
            ],
        ),
    ]
