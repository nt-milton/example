# Generated by Django 3.2.13 on 2022-07-12 18:01

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('control', '0044_copy_implementation_guides_values'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='control',
            name='implementation_guide',
        ),
    ]
