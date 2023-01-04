# Generated by Django 3.2.13 on 2022-05-06 01:52

from django.db import migrations, models

import blueprint.models.training
import laika.storage


class Migration(migrations.Migration):
    dependencies = [
        ('blueprint', '0026_objectattributeblueprint'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingBlueprint',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('airtable_record_id', models.CharField(blank=True, max_length=512)),
                ('name', models.TextField(max_length=200, unique=True)),
                (
                    'category',
                    models.CharField(
                        choices=[
                            ('Asset Management', 'Asset Management'),
                            (
                                'Business Continuity & Disaster Recovery',
                                'Business Continuity & Disaster Recovery',
                            ),
                            (
                                'Capacity & Performance Planning',
                                'Capacity & Performance Planning',
                            ),
                            ('Change Management', 'Change Management'),
                            ('Cloud Security', 'Cloud Security'),
                            ('Compliance', 'Compliance'),
                            ('Configuration Management', 'Configuration Management'),
                            ('Cryptographic Protections', 'Cryptographic Protections'),
                            (
                                'Data Classification & Handling',
                                'Data Classification & Handling',
                            ),
                            ('Embedded Technology', 'Embedded Technology'),
                            ('Endpoint Security', 'Endpoint Security'),
                            ('Human Resources Security', 'Human Resources Security'),
                            (
                                'Identification & Authentication',
                                'Identification & Authentication',
                            ),
                            ('Incident Response', 'Incident Response'),
                            ('Information Assurance', 'Information Assurance'),
                            ('Maintenance', 'Maintenance'),
                            ('Mobile Device Management', 'Mobile Device Management'),
                            ('Monitoring', 'Monitoring'),
                            ('Network Security', 'Network Security'),
                            (
                                'Physical & Environmental Security',
                                'Physical & Environmental Security',
                            ),
                            ('Privacy', 'Privacy'),
                            (
                                'Project & Resource Management',
                                'Project & Resource Management',
                            ),
                            ('Risk Management', 'Risk Management'),
                            (
                                'Secure Engineering & Architecture',
                                'Secure Engineering & Architecture',
                            ),
                            (
                                'Security & Privacy Governance',
                                'Security & Privacy Governance',
                            ),
                            (
                                'Security Awareness & Training',
                                'Security Awareness & Training',
                            ),
                            ('Security Operations', 'Security Operations'),
                            (
                                'Technology Development & Acquisition',
                                'Technology Development & Acquisition',
                            ),
                            ('Third-Party Management', 'Third-Party Management'),
                            ('Threat Management', 'Threat Management'),
                            (
                                'Vulnerability & Patch Management',
                                'Vulnerability & Patch Management',
                            ),
                            ('Web Security', 'Web Security'),
                            ('Other', 'Other'),
                        ],
                        max_length=100,
                    ),
                ),
                ('description', models.TextField()),
                (
                    'file_attachment',
                    models.FileField(
                        blank=True,
                        max_length=512,
                        storage=laika.storage.PrivateMediaStorage(),
                        upload_to=blueprint.models.training.training_file_directory_path,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField()),
            ],
            options={
                'verbose_name_plural': 'Trainings Blueprint',
            },
        ),
    ]
