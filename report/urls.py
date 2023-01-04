from django.urls import path

from .views import export_pdf_report, get_report_template

app_name = 'report'

urlpatterns = [
    path('<int:report_id>', get_report_template, name='Report template'),
    path('export/pdf', export_pdf_report, name='export_pdf_report'),
]
