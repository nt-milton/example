# Generated by Django 3.2.15 on 2022-12-15 15:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('population', '0028_alter_auditpopulation_sample_on_delete_cascade'),
    ]

    operations = [
        migrations.AddField(
            model_name='sample',
            name='name',
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
