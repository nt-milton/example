# Generated by Django 3.1.12 on 2022-02-16 02:59

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('certification', '0013_add_airtable_record_id'),
        ('blueprint', '0008_page_verbiage'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificationProxy',
            fields=[],
            options={
                'verbose_name': 'Certification',
                'verbose_name_plural': 'Certification Blueprint',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('certification.certification',),
        ),
        migrations.CreateModel(
            name='CertificationSectionProxy',
            fields=[],
            options={
                'verbose_name': 'Certification Section',
                'verbose_name_plural': 'Certification Section Blueprint',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('certification.certificationsection',),
        ),
    ]
