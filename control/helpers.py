import re
from collections import Counter

from django.db.models import Count, Q

from action_item.models import ActionItem, ActionItemStatus
from certification.models import Certification
from control.constants import (
    CONTROLS_HEALTH_FILTERS,
    CONTROLS_MONITORS_HEALTH,
    CONTROLS_QUERIES_LOOKUP,
    MAX_OWNER_LIMIT_PER_CONTROL,
    UNASSIGNED_ACTION_ITEMS,
    UNASSIGNED_OWNER_ID,
)
from feature.constants import new_controls_feature_flag
from laika.cache import cache_func
from user.models import User


def search_by_name_query(search):
    return Q(name__unaccent__icontains=search)


def search_by_display_id_query(display_id_number):
    return Q(display_id__icontains=display_id_number)


def search_by_reference_id_query(search):
    return Q(reference_id__unaccent__icontains=search)


def my_compliance_controls_enabled(organization):
    return organization.is_flag_active(new_controls_feature_flag)


def add_playbooks_controls_search_filter_query(search, filter_query):
    display_id_number = ''.join(re.findall('[0-9]+', search))
    if display_id_number:
        filter_query.add(
            search_by_name_query(search)
            | search_by_display_id_query(display_id_number),
            Q.AND,
        )
    else:
        filter_query.add(search_by_name_query(search), Q.AND)

    return filter_query


def add_my_compliance_controls_search_filter_query(search, filter_query):
    filter_query.add(
        search_by_name_query(search) | search_by_reference_id_query(search), Q.AND
    )
    return filter_query


def fill_max_owners(emails):
    if not emails:
        return [None] * MAX_OWNER_LIMIT_PER_CONTROL

    new_emails = []
    new_emails[:] = emails
    missing_new_emails = MAX_OWNER_LIMIT_PER_CONTROL - len(new_emails)

    return new_emails + ([None] * missing_new_emails)


def get_filter_owners(filters, filter_query):
    owner_ids = filters.get('owners')
    if not owner_ids:
        return filter_query

    has_unassigned = UNASSIGNED_OWNER_ID in owner_ids
    owner_ids = list(filter(lambda v: v != UNASSIGNED_OWNER_ID, owner_ids))
    owners_query = (
        Q(owner1__id__in=owner_ids)
        | Q(owner2__id__in=owner_ids)
        | Q(owner3__id__in=owner_ids)
    )

    # if owner1 is null that means owner2 and owner3 are null too
    unassigned_owners_query = Q(owner1__isnull=True)

    if has_unassigned and owner_ids:
        filter_query.add(unassigned_owners_query | owners_query, Q.AND)

    if not has_unassigned and owner_ids:
        filter_query.add(owners_query, Q.AND)

    if has_unassigned and not owner_ids:
        filter_query.add(unassigned_owners_query, Q.AND)

    return filter_query


def filter_by_certification_code_query(certification_ids):
    certification_codes = Certification.objects.filter(
        id__in=certification_ids
    ).values_list('code', flat=True)
    regex = '|'.join(certification_codes)
    return Q(reference_id__regex=f'({regex})$')


def get_filter_db(filters, filter_query, organization):
    for key, values in filters.items():
        search_criteria = CONTROLS_QUERIES_LOOKUP.get(key)

        if (
            key == 'framework'
            and values
            and my_compliance_controls_enabled(organization)
        ):
            filter_query.add(filter_by_certification_code_query(values), Q.AND)
            continue

        if search_criteria and values:
            query = Q(**{f'{search_criteria}': values})
            filter_query.add(query, Q.AND)

    return filter_query


def get_filter_search_box(filters, filter_query, organization):
    search = filters.get('search')
    if not search:
        return filter_query
    if my_compliance_controls_enabled(organization):
        return add_my_compliance_controls_search_filter_query(search, filter_query)
    return add_playbooks_controls_search_filter_query(search, filter_query)


def get_filter_health(filters, data, controls_health):
    health = filters.get('health')
    health_list = []
    if health:
        operational_options = [
            CONTROLS_MONITORS_HEALTH['NO_MONITORS'],
            CONTROLS_MONITORS_HEALTH['HEALTHY'],
        ]
        needs_attention_options = [
            CONTROLS_MONITORS_HEALTH['FLAGGED'],
            CONTROLS_MONITORS_HEALTH['NO_DATA'],
        ]
        if CONTROLS_HEALTH_FILTERS['OPERATIONAL'] in health:
            health_list.extend(operational_options)

        if CONTROLS_HEALTH_FILTERS['NEEDS_ATTENTION'] in health:
            health_list.extend(needs_attention_options)

    if health_list:
        return [
            control
            for control in data
            if control.id in controls_health
            and controls_health[control.id] in health_list
        ]

    return data


def set_assignees_to_all_child_action_items(
    current_control, action_items_override_option=None
):
    new_action_items_status = [ActionItemStatus.NEW, ActionItemStatus.PENDING]
    if current_control.owners and action_items_override_option:
        action_items_to_override = ActionItem.objects.filter(
            controls=current_control, status__in=new_action_items_status
        )

        if action_items_override_option == UNASSIGNED_ACTION_ITEMS:
            action_items_to_override = action_items_to_override.filter(assignees=None)

        for action_item in action_items_to_override:
            action_item.assignees.set(current_control.owners)


def get_filter_query(filters, names, organization):
    filter_query = Q()

    if names:
        filter_query.add(Q(name__in=names), Q.AND)

    filter_query = get_filter_owners(filters, filter_query)
    filter_query = get_filter_db(filters, filter_query, organization)
    filter_query = get_filter_search_box(filters, filter_query, organization)

    return filter_query


def get_health_stats(control_health_stats: dict):
    return dict(Counter(map(lambda x: x.lower(), control_health_stats.values())))


@cache_func
def controls_health_map_cache(controls, **kwargs):
    control_health = {}

    for control in controls:
        control_health[control.id] = control.health

    return control_health


def validate_input(update_func):
    def wrapper(*args, **kwargs):
        wrapper_input = kwargs['input']
        field = kwargs['field']
        if field in wrapper_input:
            return update_func(*args, **kwargs)

    return wrapper


def annotate_action_items_control_count():
    return ActionItem.objects.all().annotate(control_count=Count('controls__pk'))


@validate_input
def bulk_update_control_action_items_due_date(action_items, **kwargs):
    due_date = kwargs.get('input')['due_date']
    updated_ids = []

    if not due_date:
        return updated_ids

    for ai in action_items:
        if not ai.due_date or ai.control_count == 1:
            ai.due_date = due_date
            updated_ids.append(ai.id)
            continue
        if due_date < ai.due_date:
            # Update shared action items between controls
            # only when the new due_date is the one that expires first
            ai.due_date = due_date
            updated_ids.append(ai.id)

    ActionItem.objects.bulk_update(action_items, ['due_date'])

    return updated_ids


@validate_input
def bulk_update_control_action_items_owner(action_items, **kwargs):
    owner = kwargs.get('input')['owner']
    overwrite_all = kwargs.get('input')['overwrite_all']
    updated_ids = []

    if not owner:
        return updated_ids

    action_items = (
        action_items if overwrite_all else action_items.filter(assignees=None)
    )
    new_owner = User.objects.filter(email=owner).first()

    for ai in action_items:
        ai.assignees.set([new_owner])
        ai.save()
        updated_ids.append(ai.id)

    return updated_ids


class NotSubtaskFoundInMappingFile(Exception):
    pass
