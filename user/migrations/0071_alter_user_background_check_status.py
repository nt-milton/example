# Generated by Django 3.2.13 on 2022-06-08 17:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0070_update_users_preferences_alerts_frequency_soft_deleted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='background_check_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('na', 'N/A'),
                    ('pending', 'Pending'),
                    ('passed', 'Passed'),
                    ('flagged', 'Flagged'),
                    ('suspended', 'Suspended'),
                    ('canceled', 'Canceled'),
                    ('expired', 'Expired'),
                ],
                max_length=50,
                null=True,
            ),
        ),
    ]
