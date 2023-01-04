# Generated by Django 3.1.6 on 2021-06-29 21:20

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('organization', '0043_add_new_setup_steps'),
        ('dashboard', '0007_create_rule_for_dashboard_view'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
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
                ('name', models.CharField(max_length=200, unique=True)),
                ('description', models.CharField(max_length=250)),
                (
                    'task_type',
                    models.CharField(
                        choices=[('quick_start', 'Quick Start')], max_length=50
                    ),
                ),
                (
                    'task_subtype',
                    models.CharField(
                        choices=[('video', 'Video'), ('training', 'Training')],
                        max_length=25,
                    ),
                ),
                ('metadata', models.JSONField(blank=True, default=dict, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserTask',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_on', models.DateField(blank=True, null=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('seen', models.BooleanField(default=False)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('not_started', 'Not Started'),
                            ('pending', 'Pending'),
                            ('completed', 'Completed'),
                        ],
                        default='not_started',
                        max_length=50,
                    ),
                ),
                (
                    'assignee',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='organization.organization',
                    ),
                ),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to='dashboard.task'
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='usertask',
            constraint=models.UniqueConstraint(
                fields=('assignee', 'task'), name='unique_user_task'
            ),
        ),
    ]
