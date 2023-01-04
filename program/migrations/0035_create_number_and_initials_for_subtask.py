# Generated by Django 3.1.2 on 2021-03-16 18:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0034_create_number_and_initials_for_task'),
    ]

    operations = [
        migrations.AddField(
            model_name='subtask',
            name='customer_identifier',
            field=models.CharField(default='', max_length=50),
        ),
        migrations.AddField(
            model_name='subtask',
            name='number',
            field=models.IntegerField(default=0),
        ),
    ]
