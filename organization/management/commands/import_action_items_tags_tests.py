from unittest.mock import MagicMock

import pytest

from action_item.models import ActionItemTags
from organization.management.commands.import_action_items_tags import (
    import_action_item_tags,
)


@pytest.mark.django_db
def test_import_action_items_tags():
    tags = 'BC/DR Plan, Network Diagram'
    action_item_text = '''Conduct an exit interview with the employee before
    the end of their last day and retain relevant notes and feedback.'''
    import_action_item_tags(action_item_text, tags, MagicMock())
    action_item_tags = ActionItemTags.objects.all()
    assert action_item_tags.count() == 1
    assert action_item_tags.first().item_text == action_item_text
    assert action_item_tags.first().tags == tags
