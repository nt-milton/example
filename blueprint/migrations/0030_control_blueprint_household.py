# Generated by Django 3.2.13 on 2022-05-13 05:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('blueprint', '0029_object_attribute_field_rename'),
    ]

    operations = [
        migrations.AddField(
            model_name='controlblueprint',
            name='household',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='controlblueprint',
            name='reference_id',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
