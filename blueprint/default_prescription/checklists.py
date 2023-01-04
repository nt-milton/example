import logging

from action_item.models import ActionItem
from blueprint.models.checklist import ChecklistBlueprint
from organization.models import Organization, OrganizationChecklist
from tag.models import Tag

logger = logging.getLogger(__name__)


def prescribe(organization: Organization) -> list[str]:
    status_detail = []
    for index, checklist_blueprint in enumerate(
        ChecklistBlueprint.objects.iterator(), start=1
    ):
        try:
            new_checklist = get_or_create_checklist(
                organization, checklist_blueprint.checklist, checklist_blueprint.type
            )
            new_category = add_category(new_checklist, checklist_blueprint.category)
            ActionItem.objects.get_or_create(
                name=f'Step {index}',
                parent_action_item=new_checklist.action_item,
                defaults={
                    'description': checklist_blueprint.description,
                    'metadata': {
                        'isTemplate': True,
                        'category': {'id': new_category.id, 'name': new_category.name},
                    },
                },
            )

            logger.info(
                f'New checklist {new_checklist} created for '
                f'organization: {organization}'
            )
        except Exception as e:
            error_message = f'Error prescribing {checklist_blueprint}: {e}'
            status_detail.append(error_message)
            logger.warning(error_message)
    return status_detail


def add_category(checklist, category_name):
    tag, _ = Tag.objects.get_or_create(
        name__exact=category_name,
        organization=checklist.organization,
        defaults={'name': category_name},
    )
    checklist.tags.add(tag)
    return tag


def get_or_create_checklist(organization, checklist_name, checklist_type):
    try:
        checklist = OrganizationChecklist.objects.get(
            organization=organization,
            action_item__name__iexact=checklist_name,
            action_item__metadata__type=checklist_type,
        )
    except OrganizationChecklist.DoesNotExist:
        action_item = ActionItem.objects.create(
            name=checklist_name, metadata={'type': checklist_type}
        )
        checklist = OrganizationChecklist.objects.create(
            organization=organization, action_item=action_item
        )
    return checklist
