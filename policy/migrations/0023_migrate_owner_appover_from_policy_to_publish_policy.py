# Generated by Django 3.2.13 on 2022-06-10 19:16

from django.db import migrations
from django.db.models import F, Q


class Migration(migrations.Migration):
    def update_published_policy(apps, schema_editor):
        published_policy = apps.get_model('policy', 'PublishedPolicy')

        published_policy.objects.filter(Q(owned_by=None) | Q(approved_by=None)).update(
            owned_by=F('published_by'), approved_by=F('published_by')
        )

    dependencies = [
        ('policy', '0022_add_approver_and_owner_in_publish_model'),
    ]

    operations = [
        migrations.RunPython(
            update_published_policy, reverse_code=migrations.RunPython.noop
        )
    ]
