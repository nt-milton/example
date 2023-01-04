import json
import logging

from access_review.models import (
    AccessReview,
    AccessReviewVendor,
    AccessReviewVendorPreference,
)
from control.models import Control
from integration.models import ConnectionAccount
from objects.models import LaikaObject
from organization.models import Organization
from vendor.models import Vendor

logger = logging.getLogger(__name__)

CONTROL_REFERENCE_ID = 'AC-06(07)-SOC'
ACCESS_REVIEW_TYPE = 'ACCESS_REVIEW'
ACCESS_REVIEW_ACTION_ITEM_DESCRIPTION_KEY = 'AC_DESCRIPTION'
ACCESS_REVIEW_CONTINUE_LABEL_KEY = 'AC_CONTINUE_LABEL'
ACCESS_REVIEW_START_LABEL_KEY = 'AC_START_LABEL'


def return_in_scope_vendor_ids(organization):
    return AccessReviewVendorPreference.objects.filter(
        organization=organization, in_scope=True
    ).values_list('vendor_id', flat=True)


def return_integrated_vendor_ids(organization):
    connection_accounts = ConnectionAccount.objects.filter(
        status='success', organization=organization
    )
    return [
        connection_account.integration.vendor_id
        for connection_account in connection_accounts
    ]


def get_laika_object_permissions(laika_object: LaikaObject) -> str:
    data = laika_object.data
    roles = data.get('Roles')
    groups = data.get('Groups')
    return ', '.join(
        [json.dumps(permission) for permission in [groups, roles] if permission]
    )


def get_control_access_review(organization_id):
    return Control.objects.filter(
        reference_id=CONTROL_REFERENCE_ID, organization_id=organization_id
    ).first()


def get_access_review_control(organization):
    return Control.objects.filter(
        reference_id=CONTROL_REFERENCE_ID, organization_id=organization.id
    ).first()


def get_in_progress_access_review(organization: Organization):
    return (
        AccessReview.objects.filter(
            organization=organization, status=AccessReview.Status.IN_PROGRESS
        )
        .order_by('-created_at')
        .first()
    )


def get_access_review_tray_keys(organization: Organization):
    access_review_label = (
        ACCESS_REVIEW_CONTINUE_LABEL_KEY
        if get_in_progress_access_review(organization)
        else ACCESS_REVIEW_START_LABEL_KEY
    )
    return (
        ACCESS_REVIEW_TYPE,
        ACCESS_REVIEW_ACTION_ITEM_DESCRIPTION_KEY,
        access_review_label,
    )


def check_if_vendor_is_used_by_ongoing_ac(
    vendor: Vendor, organization: Organization
) -> bool:
    ongoing_access_review = get_in_progress_access_review(organization)
    if ongoing_access_review:
        access_review_vendor = AccessReviewVendor.objects.filter(
            vendor=vendor, access_review=ongoing_access_review
        ).first()
        if access_review_vendor:
            return True

    return False
