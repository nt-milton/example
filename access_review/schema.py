from typing import Any

import celery.states
import graphene
from django.db.models import BooleanField, Case, Q, Value, When
from django.db.models.functions import Lower
from django_celery_results.models import TaskResult

from access_review.constants import ACCESS_REVIEW_REMINDER
from access_review.models import AccessReviewVendorPreference
from access_review.mutations import (
    AddAccessReviewEvent,
    CompleteAccessReview,
    CreateAccessReview,
    CreateAccessReviewPreference,
    OverrideReviewers,
    RunVendorIntegrations,
    SendAccessReviewReminder,
    UpdateAccessReview,
    UpdateAccessReviewObjects,
    UpdateAccessReviewVendor,
)
from access_review.types import (
    AccessReviewPreferencesType,
    AccessReviewType,
    VendorSyncExecutionStatusType,
)
from access_review.utils import (
    get_in_progress_access_review,
    return_in_scope_vendor_ids,
    return_integrated_vendor_ids,
)
from integration.models import Integration
from laika.decorators import laika_service
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.paginator import get_paginated_result
from organization.models import Organization
from vendor.models import Vendor

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
# According to the DC-693 task (https://heylaika.atlassian.net/browse/DC-693)
WHITELISTED_VENDOR_NAMES = [
    'aws',
    'google cloud platform',
    'google workspace',
    'microsoft azure',
    'jira',
    'datadog',
    'github apps',
]


def validate_in_scope_vendors(organization: Organization):
    in_scope_vendor_ids = return_in_scope_vendor_ids(organization)
    integrated_vendor_ids = return_integrated_vendor_ids(organization)
    in_scope_to_be_removed = list(set(in_scope_vendor_ids) - set(integrated_vendor_ids))
    if len(in_scope_to_be_removed) > 0:
        ar_vendor_preference_to_deactivate = (
            AccessReviewVendorPreference.objects.filter(
                Q(vendor_id__in=in_scope_to_be_removed),
                organization=organization,
            )
        )
        ar_vendor_preference_to_deactivate.update(in_scope=False)


def build_list_vendors_filter(
    organization: Organization, filter_args: dict[str, Any]
) -> Q:
    integrable_vendor_ids = Integration.objects.all().values_list(
        'vendor_id', flat=True
    )
    in_scope = filter_args.get('inScope', False)
    vendor_ids = (
        return_in_scope_vendor_ids(organization) if in_scope else integrable_vendor_ids
    )
    whitelisted_vendor_ids = (
        Vendor.objects.annotate(lowercased_name=Lower('name'))
        .filter(lowercased_name__in=WHITELISTED_VENDOR_NAMES)
        .values_list('id', flat=True)
    )
    filtered_vendor_ids = [
        vendor_id for vendor_id in vendor_ids if vendor_id in whitelisted_vendor_ids
    ]
    search = filter_args.get('search', '')
    return Q(id__in=filtered_vendor_ids) & Q(name__unaccent__icontains=search)


class Query(object):
    access_review = graphene.Field(AccessReviewType)
    access_review_preferences = graphene.Field(
        AccessReviewPreferencesType,
        filter=graphene.JSONString(required=False),
        pagination=graphene.JSONString(required=False),
    )
    ongoing_access_review = graphene.Field(
        AccessReviewType, pagination=graphene.JSONString(required=False)
    )
    vendor_sync_execution_status = graphene.Field(
        VendorSyncExecutionStatusType, task_result_id=graphene.ID(required=True)
    )
    default_reminder_content = graphene.String(vendor_id=graphene.ID(required=True))

    @laika_service(
        permission='access_review.view_accessreview',
        exception_msg='Failed to get vendor execution status',
    )
    def resolve_default_reminder_content(self, info, vendor_id):
        user = info.context.user
        organization = user.organization
        vendor = Vendor.objects.get(id=vendor_id)
        access_review = get_in_progress_access_review(organization)
        return ACCESS_REVIEW_REMINDER.format(
            owner=f'{user.first_name} {user.last_name}',
            vendor_name=vendor.name,
            due_date=access_review.due_date.strftime('%m/%d/%y'),
        )

    @laika_service(
        permission='access_review.view_accessreview',
        exception_msg='Failed to get vendor execution status',
    )
    def resolve_vendor_sync_execution_status(self, info, task_result_id):
        task_result = TaskResult.objects.filter(
            task_id=task_result_id,
            status__in=[celery.states.SUCCESS, celery.states.FAILURE],
        ).first()
        status = task_result.status if task_result else celery.states.PENDING
        return VendorSyncExecutionStatusType(status=status)

    @laika_service(
        permission='access_review.view_accessreview',
        exception_msg='Failed to get access review',
    )
    def resolve_access_review(self, info, **kwargs):
        return get_in_progress_access_review(info.context.user.organization)

    @laika_service(
        permission='access_review.view_accessreviewpreference',
        exception_msg='Failed to get in-scope vendors',
    )
    def resolve_access_review_preferences(self, info, **kwargs):
        organization = info.context.user.organization
        validate_in_scope_vendors(organization)
        filter_args = kwargs.get('filter', dict())
        filter_params = build_list_vendors_filter(organization, filter_args)
        available_vendors = (
            Vendor.objects.filter(filter_params)
            .annotate(
                is_integrated=Case(
                    When(
                        id__in=return_integrated_vendor_ids(
                            info.context.user.organization
                        ),
                        then=Value(True),
                    ),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )
            .order_by('-is_integrated', 'name')
        )
        pagination = kwargs.get('pagination', {})
        page_size = pagination.get('pageSize', DEFAULT_PAGE_SIZE)
        page = pagination.get('page', DEFAULT_PAGE)
        paginated_result = get_paginated_result(
            rows=available_vendors, page_size=int(page_size), page=int(page)
        )
        return AccessReviewPreferencesType(
            in_scope_vendors=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )


class Mutation(object):
    override_reviewers = OverrideReviewers.Field()
    create_access_review = CreateAccessReview.Field()
    update_access_review = UpdateAccessReview.Field()
    create_access_review_preference = CreateAccessReviewPreference.Field()
    update_access_review_objects = UpdateAccessReviewObjects.Field()
    add_access_review_event = AddAccessReviewEvent.Field()
    complete_access_review = CompleteAccessReview.Field()
    run_vendor_integrations = RunVendorIntegrations.Field()
    send_access_review_reminder = SendAccessReviewReminder.Field()
    update_access_review_vendor = UpdateAccessReviewVendor.Field()
