import logging
from typing import List, Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet

from action_item.models import ActionItem
from blueprint.helpers import get_suggested_users
from blueprint.models import ActionItemBlueprint
from blueprint.models.control import ControlBlueprint
from blueprint.models.history import BlueprintHistory
from certification.models import Certification, UnlockedOrganizationCertification
from control.constants import CONTROL_TYPE, STATUS, MetadataFields
from control.models import Control, ControlGroup, ControlPillar, RoadMap
from tag.models import Tag
from user.models import User

logger = logging.getLogger(__name__)
UPLOAD_ACTION = 'Controls Prescribed'


def prescribe_controls(organization_id: str, control_ref_ids: List[str]):
    roadmap, _ = RoadMap.objects.get_or_create(organization_id=organization_id)
    controls_blueprint = ControlBlueprint.objects.filter(
        reference_id__in=control_ref_ids
    )

    suggested_owners = get_suggested_users(organization_id)

    for control_blueprint in controls_blueprint:
        # Group
        org_control_group = get_or_create_group(control_blueprint, roadmap)

        # Control Family - must have
        org_control_family = get_family(control_blueprint)

        # Control
        org_control = get_or_create_org_control(
            control_blueprint,
            organization_id,
            org_control_group,
            org_control_family,
            suggested_owners,
        )

        # Action Items
        set_action_items(
            control_blueprint, organization_id, org_control, suggested_owners
        )

        # Tags
        set_tags(control_blueprint, organization_id, org_control)

        # Certification Sections
        set_certification_sections(control_blueprint, org_control)

    # Unlock frameworks
    unlock_frameworks(controls_blueprint, organization_id)


def get_or_create_group(
    control_blueprint: ControlBlueprint, roadmap: RoadMap
) -> Optional[ControlGroup]:
    org_control_group = None

    if control_blueprint.group:
        org_control_group, _ = ControlGroup.objects.get_or_create(
            reference_id=control_blueprint.group.reference_id,
            roadmap_id=roadmap.id,
            defaults={
                'name': control_blueprint.group.name,
                'sort_order': control_blueprint.group.sort_order,
            },
        )

    return org_control_group


def get_family(control_blueprint: ControlBlueprint) -> ControlPillar:
    if control_blueprint.family:
        org_control_family, _ = ControlPillar.objects.get_or_create(
            name=control_blueprint.family.name,
            defaults={
                'acronym': control_blueprint.family.acronym,
                'description': control_blueprint.family.description,
                'illustration': control_blueprint.family.illustration,
            },
        )
        return org_control_family
    else:
        raise ObjectDoesNotExist('Unable to get control blueprint family')


def get_or_create_org_control(
    control_blueprint: ControlBlueprint,
    organization_id: str,
    group: Optional[ControlGroup],
    family: Optional[ControlPillar],
    suggested_owners: dict[str, Optional[User]],
) -> Control:
    owner = None
    if control_blueprint.suggested_owner:
        owner = suggested_owners.get(control_blueprint.suggested_owner, None)

    org_control, created = Control.objects.get_or_create(
        organization_id=organization_id,
        reference_id=control_blueprint.reference_id,
        owner1=owner,
        defaults={
            'household': control_blueprint.household,
            'name': control_blueprint.name,
            'description': control_blueprint.description,
            'status': control_blueprint.status or STATUS.get('NOT IMPLEMENTED'),
            'frequency': 'Not Applicable',
            'pillar': family,
            'implementation_guide_blueprint': control_blueprint.implementation_guide,
            'framework_tag': control_blueprint.framework_tag,
        },
    )

    if created:
        org_control.display_id = control_blueprint.display_id
        org_control.save()

    org_control.group.set([group]) if group else org_control.group.clear()
    return org_control


def set_action_items(
    control_blueprint: ControlBlueprint,
    organization_id: str,
    org_control: Control,
    suggested_owners: dict[str, Optional[User]],
) -> None:
    for action_item_blueprint in control_blueprint.action_items.all():
        owner = None
        if action_item_blueprint.suggested_owner:
            owner = suggested_owners.get(action_item_blueprint.suggested_owner, None)

        defaults = {
            'name': action_item_blueprint.name,
            'description': action_item_blueprint.description,
            'is_required': action_item_blueprint.is_required,
            'is_recurrent': action_item_blueprint.is_recurrent,
            'recurrent_schedule': action_item_blueprint.recurrent_schedule,
            'display_id': action_item_blueprint.display_id,
            'metadata': {
                f'{MetadataFields.TYPE.value}': CONTROL_TYPE,
                f'{MetadataFields.ORGANIZATION_ID.value}': str(organization_id),
                # fmt: off
                f'{MetadataFields.REFERENCE_ID.value}':
                    action_item_blueprint.reference_id,
                # fmt: on
                f'{MetadataFields.REQUIRED_EVIDENCE.value}': 'Yes'
                if action_item_blueprint.requires_evidence
                else 'No',
            },
        }

        org_action_item = (
            ActionItem.objects.filter(
                metadata__referenceId=action_item_blueprint.reference_id,
                metadata__organizationId=organization_id,
            )
            .order_by('id')
            .first()
        )

        if not org_action_item:
            org_action_item = ActionItem.objects.create(**defaults)

        if owner:
            org_action_item.assignees.set([owner])

        # Tags
        set_action_item_tags(action_item_blueprint, organization_id, org_action_item)

        org_control.action_items.add(org_action_item)
        org_control.has_new_action_items = True


def set_tags(
    control_blueprint: ControlBlueprint, organization_id: str, org_control: Control
) -> None:
    tags_to_set = []
    for tag_blueprint in control_blueprint.tags.all():
        org_tag, _ = Tag.objects.get_or_create(
            organization_id=organization_id,
            name=tag_blueprint.name,
        )
        tags_to_set.append(org_tag)

    org_control.tags.set(tags_to_set)


def set_action_item_tags(
    action_item_blueprint: ActionItemBlueprint,
    organization_id: str,
    org_action_item: ActionItem,
) -> None:
    tags_to_set = []
    for tag_blueprint in action_item_blueprint.tags.iterator():
        org_tag, _ = Tag.objects.get_or_create(
            organization_id=organization_id,
            name=tag_blueprint.name,
        )
        tags_to_set.append(org_tag)

    org_action_item.tags.set(tags_to_set)


def set_certification_sections(
    control_blueprint: ControlBlueprint, org_control: Control
) -> None:
    org_control.certification_sections.set(
        control_blueprint.certification_sections.all()
    )


def create_prescription_history_entry_controls_prescribed(
    organization, user, control_ref_ids, status
) -> BlueprintHistory:
    controls_blueprint = ControlBlueprint.objects.filter(
        reference_id__in=control_ref_ids
    )

    certification_names = ', '.join(
        list(
            Certification.objects.filter(
                code__in=controls_blueprint.values_list(
                    'framework_tag', flat=True
                ).distinct()
            ).values_list('name', flat=True)
        )
    )

    total_controls_prescribed = controls_blueprint.count()
    content_description = (
        f'{ total_controls_prescribed } Controls '
        'prescribed, within the frameworks: '
        f'{certification_names}'
    )
    new_history_entry = BlueprintHistory.objects.create(
        organization=organization,
        created_by=user,
        upload_action=UPLOAD_ACTION,
        content_description=content_description,
        status=status,
    )

    logger.info(
        f'New blueprint history entry {new_history_entry} '
        f'for organization: {organization}, for content prescription'
    )

    return new_history_entry


def unlock_frameworks(controls: QuerySet[ControlBlueprint], organization_id: str):
    certs_to_unlock = Certification.objects.filter(
        code__in=controls.values_list('framework_tag', flat=True).distinct()
    )

    for cert in certs_to_unlock:
        if not UnlockedOrganizationCertification.objects.filter(
            certification=cert, organization_id=organization_id
        ).exists():
            UnlockedOrganizationCertification.objects.update_or_create(
                certification=cert, organization_id=organization_id
            )
