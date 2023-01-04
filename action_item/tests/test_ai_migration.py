from datetime import datetime

import pytest

from action_item.models import ActionItem, ActionItemFrequency, ActionItemStatus
from control.constants import CUSTOM_PREFIX, MetadataFields
from control.models import Control, ControlPillar
from organization.models import Organization
from user.tests import create_user

REFERENCE_ID = 'AC-R-001'
CUSTOM_1 = 'AC-C-001'


@pytest.fixture()
def custom_action_item(graphql_organization):
    pillar = ControlPillar.objects.create(name='Pillar 1', acronym='PC', description='')
    control = Control.objects.create(
        organization=graphql_organization,
        display_id=1,
        name='Test Control',
        reference_id='AC-001',
        pillar_id=pillar.id,
    )

    ai1 = ActionItem.objects.create(
        name='Custom action item',
        description='My new item',
        due_date=datetime.today(),
        metadata=dict(
            referenceId='XX-C-001',
            organizationId=str(graphql_organization.id),
            isCustom=True,
            type='control',
        ),
    )

    ai2 = ActionItem.objects.create(
        name='Another custom action item',
        description='My second custom item',
        is_recurrent=True,
        due_date=datetime.today(),
        metadata=dict(
            referenceId='XX-R-001',
            organizationId=str(graphql_organization.id),
            isCustom=True,
            type='control',
        ),
    )

    ActionItem.objects.create(
        name='Third custom action item',
        description='Without control',
        due_date=datetime.today(),
        is_recurrent=True,
        metadata=dict(
            referenceId='XX-R-002',
            organizationId=str(graphql_organization.id),
            isCustom=True,
            type='control',
        ),
    )

    control.action_items.add(ai1)
    control.action_items.add(ai2)


@pytest.fixture()
def recurring_action_item(graphql_organization):
    user = create_user(
        graphql_organization, email='user1@mail.com', username='test-user-1-username'
    )
    action_item = ActionItem.objects.create_shared_action_item(
        name='action item name',
        description='Custom Description',
        recurrent_schedule=ActionItemFrequency.WEEKLY,
        due_date=datetime.today(),
        metadata=dict(
            referenceId=REFERENCE_ID,
            organizationId=str(graphql_organization.id),
            type='control',
        ),
        users=[user],
    )

    action_item.status = ActionItemStatus.COMPLETED
    action_item.save()

    # Recurring Action Items
    ActionItem.objects.create_shared_action_item(
        name='action item child 1',
        description='Another Description',
        recurrent_schedule=ActionItemFrequency.WEEKLY,
        due_date=datetime.today(),
        metadata=dict(
            organizationId=str(graphql_organization.id),
            referenceId='AC-R-002',
            type='control',
        ),
        status=ActionItemStatus.NEW,
        parent_action_item=action_item,
    )

    ActionItem.objects.create_shared_action_item(
        name='action item child 2',
        description='A better Description',
        recurrent_schedule=ActionItemFrequency.WEEKLY,
        due_date=datetime.today(),
        metadata=dict(
            organizationId=str(graphql_organization.id),
            referenceId='AC-R-003',
            type='control',
        ),
        status=ActionItemStatus.NEW,
        parent_action_item=action_item,
    )
    return action_item


@pytest.mark.django_db
def test_ai_migration_to_new_format(recurring_action_item, graphql_organization):
    recurring_children = ActionItem.objects.filter(
        is_recurrent=True,
        parent_action_item__isnull=False,
        metadata__type='control',
    )
    assert recurring_children.count() == 2
    for item in recurring_children:
        item.metadata[
            MetadataFields.REFERENCE_ID.value
        ] = item.parent_action_item.metadata[MetadataFields.REFERENCE_ID.value]
        item.save()

    updated_ais = ActionItem.objects.filter(metadata__referenceId=REFERENCE_ID)
    assert updated_ais.count() == 3

    for item in ActionItem.objects.filter(parent_action_item__isnull=False):
        assert (
            item.metadata[MetadataFields.REFERENCE_ID.value]
            == item.parent_action_item.metadata[MetadataFields.REFERENCE_ID.value]
        )


@pytest.mark.django_db
def test_custom_ai_migration_to_new_format(custom_action_item, graphql_organization):
    # This query includes custom parent action items
    custom_action_items = ActionItem.objects.filter(
        metadata__isCustom=True,
        metadata__type='control',
        metadata__organizationId__isnull=False,
        parent_action_item__isnull=True,
    )

    assert custom_action_items.count() == 3

    for item in custom_action_items:
        item.metadata['referenceIdBackup'] = item.metadata[
            MetadataFields.REFERENCE_ID.value
        ]
        item.metadata[MetadataFields.REFERENCE_ID.value] = ''
        item.save()

    custom_action_items = ActionItem.objects.filter(
        metadata__isCustom=True,
        metadata__type='control',
        metadata__organizationId__isnull=False,
    )

    for item in custom_action_items:
        organization = Organization.objects.filter(
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
        next_reference_id = ActionItem.objects.get_next_index(
            organization=organization,
            prefix=f'{acronym}-C',
        )

        item.metadata[MetadataFields.REFERENCE_ID.value] = next_reference_id
        item.metadata.pop('referenceIdBackup')
        item.save()

    updated_custom_action_items = ActionItem.objects.filter(
        metadata__isCustom=True,
        metadata__type='control',
        metadata__organizationId__isnull=False,
    )

    assert updated_custom_action_items[0].metadata[MetadataFields.REFERENCE_ID.value]

    assert (
        updated_custom_action_items[0].metadata[MetadataFields.REFERENCE_ID.value]
        == 'PC-C-001'
    )

    assert (
        updated_custom_action_items[1].metadata[MetadataFields.REFERENCE_ID.value]
        == 'PC-C-002'
    )

    assert (
        updated_custom_action_items[2].metadata[MetadataFields.REFERENCE_ID.value]
        == 'XX-C-001'
    )
