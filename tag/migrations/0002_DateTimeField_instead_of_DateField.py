# Generated by Django 3.0.7 on 2020-07-22 23:46

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('tag', '0001_initial_tag_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tag',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
