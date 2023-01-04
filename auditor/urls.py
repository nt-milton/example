from django.urls import path

from .views import (
    generate_draft_report_section_pdf,
    generate_report_pdf,
    get_draft_report_pdf,
    get_uploaded_draft_report,
)

app_name = 'auditor'
urlpatterns = [
    path('get-draft-report-pdf', get_draft_report_pdf, name='get-draft-report-pdf'),
    path(
        'get-uploaded-draft-report',
        get_uploaded_draft_report,
        name='get-uploaded-draft-report',
    ),
    path(
        'export-draft-report-section-pdf',
        generate_draft_report_section_pdf,
        name='export-draft-report-section-pdf',
    ),
    path(
        'export-report-pdf',
        generate_report_pdf,
        name='export-report-pdf',
    ),
]
