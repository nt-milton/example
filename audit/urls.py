from django.urls import path

from .views import (
    download_report,
    download_report_from_auditor,
    generate_audit_history_file,
)

app_name = 'audit'
urlpatterns = [
    path('download-report', download_report, name='download-report'),
    path(
        'download-auditor-report',
        download_report_from_auditor,
        name='download-auditor-report',
    ),
    path('generate-history', generate_audit_history_file, name='generate-history'),
]
