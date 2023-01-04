from typing import List

from django.db.models import Q

from library.constants import (
    NO_RESULT,
    NOT_ASSIGNED_USER_ID,
    NOT_RAN,
    RESULT_FOUND,
    RESULT_FOUND_UPDATED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_NO_ANSWER,
)
from library.models import Questionnaire
from organization.models import Organization
from user.models import User


def get_status_filters() -> dict:
    return dict(
        id='status',
        category='Status',
        items=[
            dict(
                id=STATUS_NO_ANSWER,
                name='No Answer',
            ),
            dict(
                id=STATUS_DRAFT,
                name='Draft',
            ),
            dict(
                id=STATUS_COMPLETED,
                name='Complete',
            ),
        ],
    )


def filter_by_status(selected_filters: dict) -> Q:
    filters = Q()
    status = selected_filters.get('status', [])
    if STATUS_NO_ANSWER in status:
        filters |= Q(library_entry__answer_text='', completed=False)
    if STATUS_DRAFT in status:
        filters |= Q(~Q(library_entry__answer_text='') & Q(completed=False))
    if STATUS_COMPLETED in status:
        filters |= Q(completed=True)
    return filters


def get_fetch_filters() -> dict:
    return dict(
        id='fetch',
        category='Fetch',
        items=[
            dict(
                id='fetched',
                name='Fetched',
            ),
            dict(
                id='not_fetched',
                name='Not Fetched',
            ),
        ],
    )


def filter_by_fetch(selected_filters: dict) -> Q:
    filters = Q()
    fetch_status_to_filter: List[str] = []
    fetched_status = [RESULT_FOUND]
    not_fetched_status = [NOT_RAN, NO_RESULT, RESULT_FOUND_UPDATED]
    fetch_filters = selected_filters.get('fetch', [])

    if not fetch_filters:
        return filters

    for fetch_filter in fetch_filters:
        if fetch_filter == 'fetched':
            fetch_status_to_filter = [*fetch_status_to_filter, *fetched_status]
        if fetch_filter == 'not_fetched':
            fetch_status_to_filter = [*fetch_status_to_filter, *not_fetched_status]
    filters &= Q(fetch_status__in=fetch_status_to_filter)
    return filters


def get_assignee_filters(
    questionnaire: Questionnaire, organization: Organization
) -> dict:
    users = User.objects.filter(
        organization=organization,
        library_questions__isnull=False,
        library_questions__questionnaires=questionnaire,
    ).distinct()
    assignees = [dict(name=user.get_full_name(), id=user.id) for user in users]

    return dict(id='assignee', category='Assignee', items=[*assignees])


def filter_by_assignee(selected_filters: dict) -> Q:
    filters = Q()
    assignee_ids = selected_filters.get('assignee', [])
    if assignee_ids:
        filters &= Q(user_assigned__id__in=assignee_ids)
        if NOT_ASSIGNED_USER_ID in assignee_ids:
            filters |= Q(user_assigned_id__isnull=True)
    return filters


def filter_by_search(selected_filters: dict) -> Q:
    filters = Q()
    search = selected_filters.get('search', '')
    if search:
        filters &= Q(text__unaccent__icontains=search) | Q(
            library_entry__answer_text__unaccent__icontains=search
        )
    return filters
