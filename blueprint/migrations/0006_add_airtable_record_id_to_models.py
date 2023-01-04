# Generated by Django 3.1.12 on 2022-02-10 16:09

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('blueprint', '0005_control_family_verbose'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionitemblueprint',
            name='airtable_record_id',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='controlblueprint',
            name='airtable_record_id',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='controlfamilyblueprint',
            name='airtable_record_id',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='controlgroupblueprint',
            name='airtable_record_id',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='implementationguideblueprint',
            name='airtable_record_id',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='tagblueprint',
            name='airtable_record_id',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AlterField(
            model_name='controlfamilyblueprint',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
