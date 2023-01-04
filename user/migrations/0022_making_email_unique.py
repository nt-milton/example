# Generated by Django 3.1.2 on 2020-11-10 18:58

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0021_first_name_length_increased'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(fields=('email',), name='unique_email'),
        ),
    ]
