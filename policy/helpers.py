from django.db.models import Q

from policy.constants import INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG
from policy.errors import (
    BAD_FORMATTED_DOCX_FILE_ERROR,
    MISSING_POLICY_OWNER_ERROR,
    WRONG_DRAFT_FILE_FORMAT_ERROR,
)


def get_policy_filters(selected_filters: dict):
    filters = Q()

    category = selected_filters.get('category', [])
    if category:
        filters &= Q(category__in=category)

    control_family = selected_filters.get('control_family', [])
    if control_family:
        filters &= Q(control_family__in=control_family)

    policy_type = selected_filters.get('type', [])
    if policy_type:
        filters &= Q(policy_type__in=policy_type)

    is_published = selected_filters.get('is_published', [])
    if is_published:
        published_status = 'published'
        is_published = map(lambda x: x == published_status, is_published)
        filters &= Q(is_published__in=is_published)

    filters = get_owners_filter(filters, selected_filters)

    tag_ids = selected_filters.get('tags', [])
    if tag_ids:
        filters &= Q(tags__id__in=tag_ids)

    return filters


def get_owners_filter(filters, selected_filters):
    owner_ids = selected_filters.get('owner', [])
    if not owner_ids:
        return filters

    unassigned = '0'
    has_unassigned_owner = unassigned in owner_ids
    unassigned_owners_query = Q(owner__isnull=True)
    owners_query = Q(owner__id__in=owner_ids)

    if has_unassigned_owner:
        owner_ids.remove(unassigned)

    if has_unassigned_owner and owner_ids:
        filters.add(unassigned_owners_query | owners_query, Q.AND)

    if has_unassigned_owner and not owner_ids:
        filters.add(unassigned_owners_query, Q.AND)

    if not has_unassigned_owner and owner_ids:
        filters.add(owners_query, Q.AND)

    return filters


def get_publish_policy_error_message(exception):
    if exception == 'MissingPolicyOAA':
        return MISSING_POLICY_OWNER_ERROR
    if exception == INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG:
        return WRONG_DRAFT_FILE_FORMAT_ERROR
    return BAD_FORMATTED_DOCX_FILE_ERROR


# TODO Delete method and remove it from the places where it is used
# when all customers start using the revamp version of policies
# where an Administrator user is not required any more.
def validate_administrator_is_empty(policy_administrator, new_controls_ff_exists):
    return not policy_administrator and not new_controls_ff_exists


def validate_input(update_func):
    def wrapper(*args, **kwargs):
        input = kwargs['input']
        field = kwargs['field']
        if field in input:
            update_func(*args, **kwargs)

    return wrapper
