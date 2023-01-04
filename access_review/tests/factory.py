from access_review.models import (
    AccessReview,
    AccessReviewObject,
    AccessReviewVendor,
    AccessReviewVendorPreference,
)
from objects.system_types import USER, resolve_laika_object_type
from objects.tests.factory import create_laika_object
from vendor.tests.factory import create_organization_vendor, create_vendor


def create_access_review(
    organization,
    access_review_file,
    status=AccessReview.Status.IN_PROGRESS,
    due_date=None,
):
    return AccessReview.objects.create(
        organization=organization,
        name='testing_access_review',
        final_report=access_review_file,
        status=status,
        due_date=due_date,
    )


def create_access_review_vendor(
    organization=None, access_review_file=None, access_review=None, vendor=None
):
    if not access_review:
        access_review = create_access_review(organization, access_review_file)
    if not vendor:
        vendor = create_vendor()
    return AccessReviewVendor.objects.create(access_review=access_review, vendor=vendor)


def create_access_review_vendor_preference(
    organization=None,
    vendor=None,
    in_scope=True,
    organization_vendor=None,
):
    if not organization_vendor:
        organization_vendor = create_organization_vendor(organization, vendor)
    return AccessReviewVendorPreference.objects.create(
        organization_vendor=organization_vendor,
        organization=organization_vendor.organization,
        vendor=organization_vendor.vendor,
        in_scope=in_scope,
    )


def create_access_review_object(
    organization,
    access_review=None,
    access_review_vendor=None,
    **kwargs,
) -> AccessReviewObject:
    if not access_review:
        access_review = create_access_review(organization, None)
    if not access_review_vendor:
        access_review_vendor = create_access_review_vendor(access_review=access_review)
    user_type = resolve_laika_object_type(organization, USER)
    laika_object = create_laika_object(
        user_type,
        None,
        {
            'First Name': 'lo',
            'Last Name': 'user',
            'Groups': 'testing',
            'Roles': 'testing',
            'Email': 'user@heylaika.com',
        },
    )
    return AccessReviewObject.objects.create(
        access_review_vendor=access_review_vendor,
        laika_object=laika_object,
        **kwargs,
    )
