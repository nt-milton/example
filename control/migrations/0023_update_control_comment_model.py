# Generated by Django 3.1.12 on 2021-08-04 19:10

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('comment', '0008_update_content_comments'),
        ('control', '0022_updating_reference_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='control',
            name='comments',
            field=models.ManyToManyField(
                related_name='control',
                through='control.ControlComment',
                to='comment.Comment',
            ),
        ),
        migrations.AlterField(
            model_name='controlcomment',
            name='comment',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='control_comments',
                to='comment.comment',
            ),
        ),
    ]
