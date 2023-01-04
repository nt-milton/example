import base64
import csv
import io
import json
import logging
from typing import Any, Iterable, List

from django.core.files import File
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from access_review.models import AccessReviewObject
from access_review.utils import get_laika_object_permissions
from laika.auth import login_required

logger = logging.getLogger(__name__)


@require_POST
@login_required
@csrf_exempt
def export_access_review_accounts(request):
    body = json.loads(request.body)
    is_confirmed = body['isConfirmed']
    access_review_vendor_id = body['accessReviewVendorID']
    return write_csv(access_review_vendor_id, is_confirmed)


def write_csv(access_review_vendor_id: str, is_confirmed: bool):
    access_review_accounts = AccessReviewObject.objects.filter(
        access_review_vendor_id=access_review_vendor_id, is_confirmed=is_confirmed
    )
    response = HttpResponse(content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(get_accounts_columns())
    for row in get_accouts_data(access_review_accounts):
        writer.writerow(row)
    return response


def get_accounts_columns() -> list[str]:
    return [
        'Account Name',
        'Connection',
        'Email',
        'Access Role/Group',
        'Marked as',
        'State',
        'Notes',
    ]


def get_accouts_data(
    access_review_accounts: list[AccessReviewObject],
) -> Iterable[List[Any]]:
    result = []
    for account in access_review_accounts:
        result.append(
            [
                account.laika_object.data.get('First Name'),
                account.laika_object.connection_account.alias,
                account.laika_object.data.get('Email'),
                get_laika_object_permissions(account.laika_object),
                account.review_status,
                'Reviewed' if account.is_confirmed else 'In Progress',
                account.notes,
            ]
        )
    return result


@require_POST
@csrf_exempt
def upload_access_review_object_attachment(request: HttpRequest, **kwargs):
    response = {}
    try:
        access_review_object = AccessReviewObject.objects.get(
            id=kwargs.get('access_review_object_id')
        )
        body = json.loads(request.body)
        original_file = body.get('file')
        attachment = io.BytesIO(base64.b64decode(original_file))
        file_name = body.get('fileName')

        if attachment:
            attachment_file = File(attachment, name=file_name)
            access_review_object.note_attachment = attachment_file
            access_review_object.save()
            response = {
                'url': access_review_object.note_attachment.url,
                'name': file_name,
            }
    except Exception:
        logger.error('Error creating object attachment')
        return HttpResponse('Error creating object attachment', status=500)

    return HttpResponse(response, content_type='application/json')
