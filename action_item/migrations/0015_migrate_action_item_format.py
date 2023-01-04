# Generated by Django 3.2.15 on 2022-10-18 19:20

import re

from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast

from control.constants import CUSTOM_PREFIX, MetadataFields


def get_next_index(action_item, organization, prefix='XX-C'):
    max_index = action_item.objects.filter(
        metadata__referenceId__startswith=prefix,
        controls__in=organization.controls.all(),
    ).aggregate(
        largest=models.Max(
            Cast(KeyTextTransform('referenceId', 'metadata'), models.TextField())
        )
    )[
        'largest'
    ]

    if max_index is not None:
        name_id = int(re.sub(r"[^0-9]+", "", max_index))
        name_id += 1
        return f"{prefix}-{name_id:03}"

    return f"{prefix}-001"


def migrate_recurring_action_items(apps, schema_editor):
    ai_model = apps.get_model('action_item', 'ActionItem')

    for item in ai_model.objects.filter(
        is_recurrent=True,
        parent_action_item__isnull=False,
        metadata__type='control',
    ):
        if item.parent_action_item.metadata.get(MetadataFields.REFERENCE_ID.value):
            item.metadata[
                MetadataFields.REFERENCE_ID.value
            ] = item.parent_action_item.metadata[MetadataFields.REFERENCE_ID.value]
            item.save()


def clean_old_reference_id(ai_model, organization_model):
    for item in ai_model.objects.filter(
        metadata__isCustom=True,
        metadata__type='control',
        metadata__organizationId__isnull=False,
        parent_action_item__isnull=True,
    ):
        organization = organization_model.objects.filter(
            id=item.metadata[MetadataFields.ORGANIZATION_ID.value]
        ).first()

        if not organization:
            continue

        item.metadata['referenceIdBackup'] = item.metadata[
            MetadataFields.REFERENCE_ID.value
        ]
        item.metadata[MetadataFields.REFERENCE_ID.value] = ''
        item.save()


def set_new_reference_id(ai_model, organization_model):
    # This query includes custom parent action items
    for item in ai_model.objects.filter(
        metadata__isCustom=True,
        metadata__type='control',
        metadata__organizationId__isnull=False,
        parent_action_item__isnull=True,
    ):
        organization = organization_model.objects.filter(
            id=item.metadata[MetadataFields.ORGANIZATION_ID.value]
        ).first()

        if not organization:
            continue

        control = item.controls.first()
        acronym = (
            control.pillar.acronym
            if control and control.pillar and control.pillar.acronym
            else CUSTOM_PREFIX
        )
        next_reference_id = get_next_index(
            ai_model,
            organization=organization,
            prefix=f'{acronym}-C',
        )

        item.metadata[MetadataFields.REFERENCE_ID.value] = next_reference_id
        item.metadata.pop('referenceIdBackup')
        item.save()


def migrate_custom_action_items(apps, schema_editor):
    organization_model = apps.get_model('organization', 'Organization')
    ai_model = apps.get_model('action_item', 'ActionItem')

    clean_old_reference_id(ai_model, organization_model)
    set_new_reference_id(ai_model, organization_model)


class Migration(migrations.Migration):
    dependencies = [
        ('action_item', '0014_add_start_date_to_control_group_and_action_items'),
    ]

    operations = [
        migrations.RunPython(
            migrate_custom_action_items, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            migrate_recurring_action_items, reverse_code=migrations.RunPython.noop
        ),
    ]
