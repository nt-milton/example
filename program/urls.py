from django.urls import path

from .views import bulk_export_evidence, export_evidence

app_name = 'program'
urlpatterns = [
    path('bulkexport', bulk_export_evidence, name='bulk-export-evidence'),
    path('export', export_evidence, name='export-evidence'),
]
