# Generated by Django 3.1.12 on 2021-11-03 21:51

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('evidence', '0026_add_one_to_one_relationship_with_link'),
        ('action_item', '0004_remove_explicit_relation'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionitem',
            name='evidences',
            field=models.ManyToManyField(
                related_name='action_items', to='evidence.Evidence'
            ),
        ),
    ]
