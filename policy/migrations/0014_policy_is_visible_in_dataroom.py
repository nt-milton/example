# Generated by Django 3.1.6 on 2021-05-07 21:15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('policy', '0013_changing_onboarding_policies_list'),
    ]

    operations = [
        migrations.AddField(
            model_name='policy',
            name='is_visible_in_dataroom',
            field=models.BooleanField(default=True),
        ),
    ]
