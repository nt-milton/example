from unittest.mock import MagicMock

import pytest

from organization.management.commands.import_subtasks_tags import import_subtask_tags
from organization.models import SubtaskTag


@pytest.mark.django_db
def test_import_subtasks_tags():
    tags = 'BC/DR Plan, Network Diagram'
    subtask_text = '''Create and upload a Network Architecture Diagram
    that shows where company data is processed and stored, what
    endpoints are involved, and what protections are in place. For more
    information and recommendations, see How-to Guide.'''
    import_subtask_tags(subtask_text, tags, MagicMock())
    subtask_tags = SubtaskTag.objects.all()
    assert subtask_tags.count() == 1
    assert subtask_tags.first().subtask_text == subtask_text
