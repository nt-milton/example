# Generated by Django 3.2.14 on 2022-08-22 18:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('seeder', '0016_adding_is_visible_seed_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='seedprofile',
            name='type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'No Type'),
                    ('playbooks', 'Playbooks'),
                    ('my_compliance', 'My Compliance'),
                ],
                default='',
                max_length=500,
                verbose_name='Program Type',
            ),
        ),
    ]
