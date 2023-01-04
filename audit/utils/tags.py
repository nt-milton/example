import logging

from action_item.models import ActionItem, ActionItemTags
from organization.models import Organization, SubtaskTag
from program.models import SubTask
from tag.models import Tag

logger = logging.getLogger('audit_utils')


def link_subtasks_evidence_to_tags(organization_id: str) -> None:
    subtasks = SubTask.objects.filter(task__program__organization_id=organization_id)
    subtasks_tags = SubtaskTag.objects.all()
    for subtask in subtasks:
        org_subtask_text = subtask.text.strip().lower()
        tags_text_list = [
            subtask_tag.tags
            for subtask_tag in subtasks_tags
            if subtask_tag.subtask_text.lower() == org_subtask_text
        ]

        if not tags_text_list:
            continue

        tags_text = tags_text_list[0]
        logger.info(
            f'Linking subtask: {subtask.id} to tags:{tags_text} '
            f'for org:{organization_id}'
        )
        tags_strings = [t.strip() for t in tags_text.split(',')]
        tags = []
        for t in tags_strings:
            tag, _ = Tag.objects.get_or_create(organization_id=organization_id, name=t)
            tags.append(tag)

        subtask.tags.add(*tags)

        if not subtask.has_evidence:
            continue

        for e in subtask.evidence.all():
            logger.info(
                f'Linking evidence: {e.id} to tags:{tags_text}'
                f' for org:{organization_id}'
            )
            e.tags.add(*subtask.tags.all())


def link_audit_tags_to_action_items_evidence(organization: Organization) -> None:
    action_items = ActionItem.objects.filter(evidences__organization=organization)
    action_item_tags = ActionItemTags.objects.all()

    for item in action_items:
        item_desc = item.description.strip().lower()
        tags_text_list = [
            item_tag.tags
            for item_tag in action_item_tags
            if item_tag.item_text.strip().lower() == item_desc
        ]

        if not tags_text_list:
            continue

        tags_text = tags_text_list[0]
        logger.info(
            f'Linking action item: {item.id} evidence to tags:{tags_text} '
            f'for org:{organization.id}'
        )
        tags_strings = [t.strip() for t in tags_text.split(',')]
        tags = []
        for t in tags_strings:
            tag, _ = Tag.objects.get_or_create(organization_id=organization.id, name=t)
            tags.append(tag)

        for e in item.evidences.all():
            logger.info(
                f'Linking evidence: {e.id} to tags:{tags_text}'
                f' for org:{organization.id}'
            )
            e.tags.add(*tags)
