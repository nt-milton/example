import re

from django.db import models

from control.models import ControlGroup, RoadMap

untitled_control_group = 'Untitled Group'
NEW_GROUP_PREFIX = 'XX'
FIRST_SORT_ORDER = 1
SECOND_SORT_ORDER = 2
natural_number_pattern = r'[^0-9]+'


def get_untitled_groups(roadmap: RoadMap):
    untitled_control_groups = ControlGroup.objects.filter(
        roadmap=roadmap, name__icontains=untitled_control_group
    )
    current_length = len(untitled_control_groups)

    return None if current_length == 0 else current_length


def get_untitled_name(roadmap: RoadMap):
    length = get_untitled_groups(roadmap)
    name = untitled_control_group

    if length:
        name = untitled_control_group + f' {length}'

    return name


def get_control_groups(roadmap: RoadMap):
    return ControlGroup.objects.filter(
        roadmap=roadmap,
    )


def shift_new_group_to_top(new_group: ControlGroup, roadmap: RoadMap):
    new_group.sort_order = FIRST_SORT_ORDER
    new_group.save()

    roadmap_groups = roadmap.groups.exclude(pk=new_group.pk).order_by('sort_order')

    for index, group in enumerate(roadmap_groups):
        group.sort_order = index + SECOND_SORT_ORDER
        group.save()


def get_reference_id(roadmap: RoadMap):
    max_index_num = 0
    max_reference_id = ControlGroup.objects.filter(
        reference_id__startswith=NEW_GROUP_PREFIX, roadmap_id=roadmap.id
    ).aggregate(largest=models.Max('reference_id'))['largest']

    if max_reference_id:
        max_index_num = int(re.sub(natural_number_pattern, '', max_reference_id))
    name_id = max_index_num + 1
    return f'{NEW_GROUP_PREFIX}-{name_id:02}'
