from django.urls import path

from blueprint import views

app_name = 'blueprint'
urlpatterns = [
    path(
        '<int:evidence_metadata_id>/download_evidence_metadata',
        views.download_evidence_metadata,
        name='download_evidence_metadata',
    )
]
