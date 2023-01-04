# Generated by Django 3.1.2 on 2020-11-09 14:43

import logging

from django.db import migrations
from django.db.models import Q

import evidence.constants as constants
from laika.utils.files import get_html_file_content

logger = logging.getLogger('evidence_migration')


def fill_evidence_text(apps, schema_editor):
    Evidence = apps.get_model('evidence', 'Evidence')
    evidence = Evidence.objects.filter(
        Q(type=constants.LAIKA_PAPER)
        & (Q(evidence_text__isnull=True) | Q(evidence_text=''))
    )
    evidence_id = ''
    try:
        for e in evidence:
            evidence_id = e.id
            logger.info(f'Getting file content for evidence: {evidence_id}')
            e.evidence_text = get_html_file_content(e.file, evidence_id)

        Evidence.objects.bulk_update(evidence, ['evidence_text'])
    except Exception as e:
        logger.exception(f'Failed filling evidence: {policy_id} text with error {e}')


class Migration(migrations.Migration):
    dependencies = [
        ('evidence', '0015_making_field_optional'),
    ]

    operations = [migrations.RunPython(fill_evidence_text)]
