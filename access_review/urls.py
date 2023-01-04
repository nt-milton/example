from django.urls import path

from access_review.views import (
    export_access_review_accounts,
    upload_access_review_object_attachment,
)

app_name = 'access_review'

urlpatterns = [
    path(
        'export/accounts/report',
        export_access_review_accounts,
        name='export_accounts_report',
    ),
    path(
        '<str:access_review_object_id>/upload',
        upload_access_review_object_attachment,
        name='upload_access_review_object_attachment',
    ),
]
