# Generated by Django 3.1.6 on 2021-05-21 14:27

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('seeder', '0005_add_audit_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldworkSeed',
            fields=[],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('seeder.seed',),
        ),
    ]
