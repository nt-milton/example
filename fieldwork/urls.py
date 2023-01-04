from django.urls import path

from .views import export_attachment, export_attachment_auditor, generate_report

app_name = 'fieldwork'
urlpatterns = [
    path('attachment/export', export_attachment, name='fieldwork'),
    path(
        'attachment/auditor-export',
        export_attachment_auditor,
        name='download-attachment-auditor',
    ),
    path('generate-report', generate_report, name='generate-report'),
]
