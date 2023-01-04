# Generated by Django 3.0.2 on 2020-01-23 17:06

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('created_at', models.DateField(auto_now_add=True)),
                ('updated_at', models.DateField(auto_now=True)),
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('website', models.CharField(blank=True, max_length=2000, unique=True)),
                (
                    'tier',
                    models.CharField(
                        blank=True,
                        choices=[('P', 'Premium'), ('S', 'Starter'), ('T', 'Teaser')],
                        max_length=2,
                    ),
                ),
                ('is_public_company', models.BooleanField(blank=True, null=True)),
                ('number_of_employees', models.IntegerField(blank=True, null=True)),
                ('business_inception_date', models.DateField(blank=True, null=True)),
                ('product_or_service_description', models.TextField(blank=True)),
            ],
        ),
    ]
