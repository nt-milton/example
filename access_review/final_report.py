import io
import zipfile
from datetime import datetime
from os.path import basename

from access_review.models import (
    AccessReview,
    AccessReviewObject,
    AccessReviewPreference,
    AccessReviewUserEvent,
    AccessReviewVendor,
)
from access_review.utils import get_laika_object_permissions
from laika.utils.pdf import render_template_to_pdf
from objects.models import LaikaObject
from user.models import User


def get_full_name(first_name: str, last_name: str) -> str:
    return f'{first_name} {last_name}'.strip()


def get_user_full_name(user: User) -> str:
    return get_full_name(user.first_name, user.last_name)


def get_last_review_event(
    access_review_object: AccessReviewObject,
) -> AccessReviewUserEvent:
    return (
        access_review_object.access_review_user_events.filter(
            event=AccessReviewUserEvent.EventType.REVIEWED_ACCOUNTS
        )
        .order_by('-event_date')
        .first()
    )


def get_account_name_from_lo(laika_object: LaikaObject) -> str:
    lo_data = laika_object.data
    full_name = get_full_name(
        lo_data.get('First Name', ''), lo_data.get('Last Name', '')
    )
    return lo_data.get('Display Name', full_name)


def get_final_access_review_object(access_review_object: AccessReviewObject) -> dict:
    laika_object = access_review_object.laika_object
    account_name = get_account_name_from_lo(laika_object)
    review_event = get_last_review_event(access_review_object)
    return {
        'account_name': account_name,
        'user_email': laika_object.data.get('Email'),
        'reviewed_by': review_event.user,
        'roles': get_laika_object_permissions(laika_object),
        'time_of_review': review_event.event_date,
        'notes': access_review_object.notes,
    }


def get_laika_objects_map(access_review_objects, access_review_vendor, status):
    access_review_objects = access_review_objects.filter(
        access_review_vendor__vendor=access_review_vendor.vendor, review_status=status
    )
    final_access_review_objects = []
    for access_review_object in access_review_objects:
        final_access_review_object = get_final_access_review_object(
            access_review_object
        )
        final_access_review_objects.append(final_access_review_object)
    return final_access_review_objects


def get_zip_info_from_name(filename: str) -> zipfile.ZipInfo:
    now = datetime.now().timetuple()
    return zipfile.ZipInfo(filename=filename, date_time=now)  # type: ignore


def generate_evidence_file(
    access_review_object: AccessReviewObject,
    vendor_evidence_path: str,
    zip_file: zipfile.ZipFile,
):
    access_review_vendor = access_review_object.access_review_vendor
    vendor_name = access_review_vendor.vendor.name
    vendor_evidence_path = f'evidences/{vendor_name}'
    if access_review_object.evidence:
        evidence_filename = (
            f'{vendor_evidence_path}/account_level_evidences'
            f'/{basename(access_review_object.evidence.name)}'
        )
        with (
            zip_file.open(
                get_zip_info_from_name(evidence_filename), 'w'
            ) as account_evidence,
            access_review_object.evidence.open('rb') as content,
        ):
            account_evidence.write(content.read())


def generate_note_attachment_file(
    access_review_object: AccessReviewObject,
    vendor_evidence_path: str,
    zip_file: zipfile.ZipFile,
):
    if access_review_object.note_attachment:
        note_filename = (
            f'{vendor_evidence_path}/additional_notes'
            f'/{basename(access_review_object.note_attachment.name)}'
        )
        with (
            zip_file.open(get_zip_info_from_name(note_filename), 'w') as note,
            access_review_object.note_attachment.open('rb') as content,
        ):
            note.write(content.read())


def generate_zip_for_evidences(
    access_review: AccessReview,
    access_review_summary: io.BytesIO,
    access_review_objects: list[AccessReviewObject],
) -> io.BytesIO:
    zip_buffer = io.BytesIO()
    final_report_name = f'Summary Report - {access_review.name}.pdf'
    with zipfile.ZipFile(zip_buffer, mode='w') as zip_file:
        with zip_file.open(
            get_zip_info_from_name(final_report_name), 'w'
        ) as final_report:
            final_report.write(access_review_summary.getvalue())
        for access_review_object in access_review_objects:
            access_review_vendor = access_review_object.access_review_vendor
            vendor_name = access_review_vendor.vendor.name
            vendor_evidence_path = f'evidences/{vendor_name}'
            generate_evidence_file(access_review_object, vendor_evidence_path, zip_file)
            generate_note_attachment_file(
                access_review_object, vendor_evidence_path, zip_file
            )
    return zip_buffer


def generate_final_evidence_file(
    access_review: AccessReview,
    access_review_preference: AccessReviewPreference,
    vendors: list[dict],
    completed_by: User,
) -> io.BytesIO:
    return io.BytesIO(
        render_template_to_pdf(
            template='access_review_summary.html',
            context={
                'organization_name': access_review.organization.name,
                'access_review_name': access_review.name,
                'created_at': access_review.created_at,
                'created_by': (
                    get_user_full_name(access_review.created_by)
                    if access_review.created_by
                    else 'N/A'
                ),
                'completed_at': datetime.now(),
                'completed_by': get_user_full_name(completed_by),
                'frequency_of_review': access_review_preference.frequency,
                'vendors': vendors,
            },
            orientation='Landscape',
        )
    )


def create_access_review_summary(
    access_review: AccessReview, completed_by: User
) -> io.BytesIO:
    access_review_preference = AccessReviewPreference.objects.filter(
        organization=access_review.organization
    ).first()
    access_review_vendors = AccessReviewVendor.objects.filter(
        access_review=access_review,
    ).select_related('vendor')
    vendors = []
    access_review_objects = AccessReviewObject.objects.filter(
        access_review_vendor__access_review=access_review
    ).order_by('access_review_vendor__vendor__name')
    for access_review_vendor in access_review_vendors:
        unchanged = get_laika_objects_map(
            access_review_objects,
            access_review_vendor,
            AccessReviewObject.ReviewStatus.UNCHANGED,
        )
        modified = get_laika_objects_map(
            access_review_objects,
            access_review_vendor,
            AccessReviewObject.ReviewStatus.MODIFIED,
        )
        revoked = get_laika_objects_map(
            access_review_objects,
            access_review_vendor,
            AccessReviewObject.ReviewStatus.REVOKED,
        )
        number_of_accounts = len(unchanged) + len(modified) + len(revoked)
        vendors.append(
            {
                'name': access_review_vendor.vendor.name,
                'status': access_review_vendor.status,
                'unchanged': unchanged,
                'modified': modified,
                'revoked': revoked,
                'number_of_accounts': number_of_accounts,
            }
        )
    access_review_summary = generate_final_evidence_file(
        access_review,
        access_review_preference,
        vendors,
        completed_by,
    )
    return generate_zip_for_evidences(
        access_review, access_review_summary, access_review_objects
    )
