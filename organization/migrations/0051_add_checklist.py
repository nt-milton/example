# Generated by Django 3.1.12 on 2021-09-28 16:54

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('action_item', '0001_initial'),
        ('tag', '0003_tag_is_manual'),
        ('organization', '0050_increase_description_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationChecklist',
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
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='OrganizationChecklistItem',
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
                ('is_template', models.BooleanField(blank=True, default=False)),
                (
                    'action_item',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='action_item.actionitem',
                    ),
                ),
                (
                    'organization_checklist',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='organization.organizationchecklist',
                    ),
                ),
                (
                    'task_type',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to='tag.tag'
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='organizationchecklist',
            name='items',
            field=models.ManyToManyField(
                related_name='checklist_items',
                through='organization.OrganizationChecklistItem',
                to='action_item.ActionItem',
            ),
        ),
        migrations.AddField(
            model_name='organizationchecklist',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='organization.organization',
            ),
        ),
    ]
