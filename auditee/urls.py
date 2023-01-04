from django.urls import path

from .views import get_uploaded_draft_report

app_name = 'auditee'
urlpatterns = [
    path(
        'get-uploaded-draft-report',
        get_uploaded_draft_report,
        name='get-uploaded-draft-report',
    )
]
