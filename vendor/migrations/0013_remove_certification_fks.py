# Generated by Django 3.0.7 on 2020-07-10 19:43

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('vendor', '0012_add_vendor_certification_model'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vendor',
            name='global_certifications',
        ),
        migrations.DeleteModel(
            name='VendorCertification',
        ),
    ]
