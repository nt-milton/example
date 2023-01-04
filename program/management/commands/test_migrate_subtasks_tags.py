from unittest.mock import MagicMock

import pytest

from program.management.commands.migrate_subtasks_tags import link_subtask_tags
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
        text='Subtask with tags',
        status='completed',
        group='documentation',
        sort_index=1,
        badges='technical',
    )


@pytest.mark.django_db
def test_migrate_subtasks_tags(graphql_organization, task, subtask):
    tags = 'BC/DR Plan, Network Diagram'
    link_subtask_tags(graphql_organization.id, task.id, subtask.id, tags, MagicMock())
    updated_subtask = SubTask.objects.filter(id=subtask.id).first()
    subtask_tags = updated_subtask.tags
    assert subtask_tags.count() == 2

    for tag in subtask_tags.all():
        assert tag.name in ['BC/DR Plan', 'Network Diagram']
