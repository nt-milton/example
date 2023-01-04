import pytest

from action_item.models import ActionItem, ActionItemTags
from audit.utils.tags import (
    link_audit_tags_to_action_items_evidence,
    link_subtasks_evidence_to_tags,
)
from organization.models import SubtaskTag
from program.models import SubTask
from program.tests import create_program, create_task


@pytest.fixture
def program(graphql_organization):
    return create_program(
        organization=graphql_organization,
        name='Privacy Program',
        description='This is an example of program',
    )


@pytest.fixture
def task(graphql_organization, program):
    return create_task(organization=graphql_organization, program=program)


@pytest.fixture
def subtask(task):
    return SubTask.objects.create(
        task=task,
        text='Subtask with tags ',
        status='completed',
        group='documentation',
        sort_index=1,
        badges='technical',
    )


@pytest.mark.django_db
def test_link_subtasks_evidence_to_tags(graphql_organization, task, subtask):
    tags = 'BC/DR Plan, Network Diagram'

    SubtaskTag.objects.create(subtask_text='subtask with Tags', tags=tags)
    link_subtasks_evidence_to_tags(graphql_organization.id)
    updated_subtask = SubTask.objects.filter(
        task__program__organization_id=graphql_organization
    ).first()
    subtask_tags = updated_subtask.tags
    assert subtask_tags.count() == 2

    for tag in subtask_tags.all():
        assert tag.name in ['BC/DR Plan', 'Network Diagram']


@pytest.mark.django_db
def test_link_action_item_evidence_to_tags(
    graphql_organization, action_item, action_item_evidence
):
    tags = 'BC/DR Plan, Network Diagram'

    ActionItemTags.objects.create(item_text='action item test', tags=tags)
    link_audit_tags_to_action_items_evidence(graphql_organization)
    updated_action_item = ActionItem.objects.filter(
        evidences__organization=graphql_organization
    ).first()
    item_evidence = updated_action_item.evidences.all().first()

    assert item_evidence.tags.count() == 2

    for tag in item_evidence.tags.all():
        assert tag.name in ['BC/DR Plan', 'Network Diagram']
