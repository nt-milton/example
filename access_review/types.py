from datetime import datetime

import graphene
from django.db.models import Case, Value, When
from graphene_django import DjangoObjectType

from access_review.models import (
    AccessReview,
    AccessReviewObject,
    AccessReviewPreference,
    AccessReviewUserEvent,
    AccessReviewVendor,
    AccessReviewVendorPreference,
)
from access_review.utils import (
    get_control_access_review,
    return_in_scope_vendor_ids,
    return_integrated_vendor_ids,
)
from integration.models import ConnectionAccount
from integration.utils import get_last_run
from laika.types import BaseResponseType, PaginationResponseType
from objects.models import LaikaObject
from objects.models import LaikaObjectType as ObjectType
from objects.schema import LaikaObjectDataType
from pentest.views import _truncate_name
from user.constants import USER_ROLES
from user.types import UserType
from vendor.models import Vendor
from vendor.schema import OrganizationVendorType, VendorType


class AccessReviewPreferenceType(DjangoObjectType):
    class Meta:
        model = AccessReviewPreference
        fields = ('frequency', 'criticality', 'due_date')

    frequency = graphene.String()
    criticality = graphene.String()
    due_date = graphene.DateTime()


class AccessReviewObjectType(DjangoObjectType):
    class Meta:
        model = AccessReviewObject
        fields = (
            'id',
            'laika_object',
            'evidence',
            'review_status',
            'notes',
            'original_access',
            'final_snapshot',
            'is_confirmed',
        )

    id = graphene.ID()
    laika_object = graphene.Field(
        LaikaObjectDataType, id=graphene.String(), object_type=graphene.String()
    )
    review_status = graphene.String()
    notes = graphene.String()
    original_access = graphene.JSONString()
    final_snapshot = graphene.JSONString()
    is_confirmed = graphene.Boolean()
    evidence = graphene.String()
    note_attachment = graphene.String()
    note_attachment_name = graphene.String()

    def resolve_note_attachment(self, info):
        if self.note_attachment:
            return self.note_attachment.url
        return None

    def resolve_note_attachment_name(self, info):
        if self.note_attachment:
            return _truncate_name(self.note_attachment.name)
        return None

    def resolve_evidence(self, info):
        if self.evidence:
            return self.evidence.url
        return None

    def resolve_laika_object(self, info):
        return LaikaObject.objects.filter(id=self.laika_object.id).first()


class AccessReviewVendorType(DjangoObjectType):
    class Meta:
        model = AccessReviewVendor
        fields = ('id', 'access_review', 'vendor', 'synced_at', 'source', 'status')

    id = graphene.ID()
    source = graphene.String()
    status = graphene.String()
    synced_at = graphene.DateTime()
    vendor = graphene.Field(VendorType)
    access_review_objects = graphene.List(AccessReviewObjectType)
    reviewers = graphene.List(UserType)
    is_enabled_for_current_user = graphene.Boolean()

    def resolve_is_enabled_for_current_user(self, info):
        user = info.context.user
        if user.role == USER_ROLES['ADMIN']:
            return True
        organization = user.organization
        reviewers = AccessReviewVendorPreference.objects.get(
            vendor=self.vendor,
            organization=organization,
        ).reviewers.all()
        return user in reviewers

    def resolve_access_review_objects(self, info):
        return (
            AccessReviewObject.objects.filter(access_review_vendor=self)
            .annotate(
                status_priority=Case(
                    When(
                        review_status=AccessReviewObject.ReviewStatus.MODIFIED,
                        then=Value(0),
                    ),
                    When(
                        review_status=AccessReviewObject.ReviewStatus.REVOKED,
                        then=Value(1),
                    ),
                    default=Value(2),
                )
            )
            .order_by('status_priority')
        )

    def resolve_reviewers(self, info):
        organization = info.context.user.organization
        vendor_preferences = AccessReviewVendorPreference.objects.get(
            vendor=self.vendor,
            organization=organization,
        ).reviewers.all()
        return vendor_preferences


class AccessReviewType(DjangoObjectType):
    class Meta:
        model = AccessReview
        fields = (
            'id',
            'name',
            'created_at',
            'due_date',
            'completed_at',
            'status',
            'notes',
        )

    id = graphene.ID()
    name = graphene.String()
    created_at = graphene.DateTime()
    completed_at = graphene.DateTime()
    due_date = graphene.DateTime()
    status = graphene.String()
    notes = graphene.String()
    final_report_url = graphene.String()
    help_modal_opened = graphene.Boolean()
    access_review_vendors = graphene.List(AccessReviewVendorType, vendor=graphene.Int())
    control = graphene.String()

    def resolve_final_report_url(self, info):
        if self.final_report:
            return self.final_report.url
        return None

    def resolve_help_modal_opened(self, info):
        return AccessReviewUserEvent.objects.filter(
            access_review=self.id,
            user=info.context.user.id,
            event=AccessReviewUserEvent.EventType.HELP_MODAL_OPENED,
        ).exists()

    def resolve_access_review_vendors(self, info, **kwargs):
        filters = {}
        if vendor := kwargs.get('vendor'):
            filters = {'vendor_id': vendor}

        return AccessReviewVendor.objects.filter(access_review_id=self.id, **filters)

    def resolve_control(self, info):
        organization = info.context.user.organization
        control = get_control_access_review(organization.id)
        if not control:
            return
        return control.id


class AccessReviewVendorPreferenceType(DjangoObjectType):
    class Meta:
        model = AccessReviewVendorPreference
        fields = ('id', 'organization_vendor', 'vendor', 'in_scope', 'reviewers')

    id = graphene.UUID()
    organization_vendor = graphene.Field(OrganizationVendorType)
    vendor = graphene.Field(VendorType)
    in_scope = graphene.Boolean()
    reviewers = graphene.List(UserType)

    def resolve_reviewers(self, info):
        return self.reviewers.all()


def get_last_data_sync(connection_accounts):
    return [
        datetime.strptime(get_last_run(ca), '%Y-%m-%d') if get_last_run(ca) else None
        for ca in connection_accounts
    ]


class AccessReviewUserEventType(DjangoObjectType):
    class Meta:
        model = AccessReviewUserEvent
        fields = ('id', 'access_review', 'user', 'event')

    id = graphene.ID()
    access_review = graphene.Field(AccessReviewType)
    user = graphene.Field(UserType)
    event = graphene.String()


class InScopeVendorType(VendorType, graphene.ObjectType):
    class Meta:
        model = Vendor

    is_in_scope = graphene.Boolean()
    is_integrated = graphene.Boolean()
    accounts = graphene.Int()
    last_data_sync = graphene.DateTime()
    reviewers = graphene.List(UserType)

    def resolve_is_in_scope(self, info):
        in_scope_vendor_ids = return_in_scope_vendor_ids(info.context.user.organization)
        return self.id in in_scope_vendor_ids

    def resolve_is_integrated(self, info):
        integrated_vendor_ids = return_integrated_vendor_ids(
            info.context.user.organization
        )
        return self.id in integrated_vendor_ids

    def resolve_reviewers(self, info):
        try:
            organization = info.context.user.organization
            vendor_preferences = AccessReviewVendorPreference.objects.get(
                vendor=self,
                organization=organization,
            ).reviewers.all()
            return vendor_preferences
        except AccessReviewVendorPreference.DoesNotExist:
            return []

    def resolve_accounts(self, info):
        connection_accounts = ConnectionAccount.objects.filter(
            integration__vendor=self, organization=info.context.user.organization
        )
        object_types_ids = ObjectType.objects.filter(
            type_name__in=['user', 'service_account']
        ).values('id')
        accounts = LaikaObject.objects.filter(
            connection_account__in=connection_accounts,
            object_type_id__in=object_types_ids,
            deleted_at__isnull=True,
        ).count()
        return accounts

    def resolve_last_data_sync(self, info):
        connection_accounts = ConnectionAccount.objects.filter(
            integration__vendor=self, organization=info.context.user.organization
        )
        last_runs = get_last_data_sync(connection_accounts)
        if not all(last_runs) or not last_runs:
            return None
        return max(last_runs)


class AccessReviewPreferencesType(BaseResponseType):
    in_scope_vendors = graphene.List(InScopeVendorType)
    preferences = graphene.Field(AccessReviewPreferenceType)
    pagination = graphene.Field(PaginationResponseType)
    completed_access_reviews = graphene.List(AccessReviewType)

    def resolve_preferences(self, info):
        return AccessReviewPreference.objects.filter(
            organization=info.context.user.organization,
        ).first()

    def resolve_completed_access_reviews(self, info):
        return AccessReview.objects.filter(
            organization=info.context.user.organization, status=AccessReview.Status.DONE
        )


class InScopeVendorResponseType(graphene.ObjectType):
    data = graphene.List(InScopeVendorType)
    pagination = graphene.Field(PaginationResponseType)


class VendorSyncExecutionStatusType(graphene.ObjectType):
    status = graphene.String()
