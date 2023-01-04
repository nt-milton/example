import io
from typing import Iterator

from django.core.files import File

from access_review.final_report import get_account_name_from_lo
from access_review.models import AccessReviewObject, AccessReviewVendorPreference
from access_review.utils import get_laika_object_permissions
from integration.models import ConnectionAccount
from laika.utils.pdf import render_template_to_pdf
from objects.system_types import SERVICE_ACCOUNT, USER


def get_connection_account_objects(
    connection_account: ConnectionAccount,
) -> Iterator[AccessReviewObject]:
    lo_ids = connection_account.laika_objects.filter(
        object_type__type_name__in=[USER.type, SERVICE_ACCOUNT.type]
    ).values_list('id')
    return AccessReviewObject.objects.filter(laika_object__id__in=[lo_ids]).exclude(
        review_status=AccessReviewObject.ReviewStatus.REVOKED
    )


def create_evidence_for_access_review_object(
    access_review_object: AccessReviewObject,
) -> io.BytesIO:
    access_review_vendor = access_review_object.access_review_vendor
    access_review = access_review_vendor.access_review
    access_review_vendor_preference = AccessReviewVendorPreference.objects.get(
        organization=access_review.organization,
        vendor=access_review_vendor.vendor,
    )
    reviewers = [
        f'{reviewer.first_name} {reviewer.last_name}'
        for reviewer in access_review_vendor_preference.reviewers.all()
    ]
    laika_object = access_review_object.laika_object
    return io.BytesIO(
        render_template_to_pdf(
            template='account_level_evidence.html',
            context={
                'access_review_name': access_review.name,
                'vendor_name': access_review_vendor.vendor.name,
                'account_name': get_account_name_from_lo(laika_object),
                'account_id': laika_object.id,
                'email': laika_object.data.get('Email'),
                'updated_at': laika_object.updated_at,
                'update_type': access_review_object.review_status,
                'is_deleted': bool(laika_object.deleted_at),
                'reviewers': reviewers,
                'update_details': {
                    'original_state': access_review_object.original_access,
                    'current_state': access_review_object.latest_access or '',
                },
            },
        )
    )


def get_access_review_object_updates(
    access_review_objects: Iterator[AccessReviewObject],
) -> tuple[dict, set]:
    updated_objects = {}
    accesses_to_be_reviewed = set()
    for access_review_object in access_review_objects:
        laika_object = access_review_object.laika_object
        original_access = access_review_object.original_access
        latest_access = access_review_object.latest_access
        current_access = get_laika_object_permissions(laika_object)
        is_deleted = laika_object.deleted_at
        is_modified = not is_deleted and (
            original_access != current_access and original_access != latest_access
        )
        access_has_been_updated = bool(is_deleted) or (
            current_access != latest_access
            if latest_access
            else current_access != original_access
        )
        id = str(access_review_object.id)
        if access_has_been_updated:
            accesses_to_be_reviewed.add(id)
        if is_modified:
            updated_objects[id] = AccessReviewObject.ReviewStatus.MODIFIED
        elif is_deleted:
            updated_objects[id] = AccessReviewObject.ReviewStatus.REVOKED
    return updated_objects, accesses_to_be_reviewed


def update_access_review_objects(updated_objects: dict):
    for object_id, status in updated_objects.items():
        access_review_obj = AccessReviewObject.objects.get(id=object_id)
        access_review_obj.review_status = status
        laika_object = access_review_obj.laika_object
        if status == AccessReviewObject.ReviewStatus.MODIFIED:
            latest_access = get_laika_object_permissions(laika_object)
            access_review_obj.latest_access = latest_access
        evidence = create_evidence_for_access_review_object(access_review_obj)
        account_name = get_account_name_from_lo(laika_object)
        account_identifier = account_name or access_review_obj.id
        access_review_obj.evidence = File(
            file=evidence, name=f'Account Evidence - {account_identifier}.pdf'
        )
        access_review_obj.save()


def set_access_review_objects_for_review(access_review_object_ids: set[str]):
    AccessReviewObject.objects.filter(id__in=access_review_object_ids).update(
        is_confirmed=False
    )


def reconcile_access_review_objects(connection_account: ConnectionAccount):
    access_review_objects = get_connection_account_objects(connection_account)
    updated_objects, accesses_to_be_reviewed = get_access_review_object_updates(
        access_review_objects
    )
    update_access_review_objects(updated_objects)
    set_access_review_objects_for_review(accesses_to_be_reviewed)
