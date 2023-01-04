# Generated by Django 3.1.12 on 2021-07-15 21:40

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('control', '0014_add_control_pillars'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImplementationGuide',
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
                ('name', models.CharField(blank=True, max_length=255)),
                ('text', models.TextField(blank=True)),
                ('is_system', models.BooleanField(blank=True)),
            ],
        ),
        migrations.AddField(
            model_name='control',
            name='implementation_guide',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='control',
                to='control.implementationguide',
            ),
        ),
    ]
