from django.urls import path

from .views import download_ddp, export_ddp

app_name = 'concierge'
urlpatterns = [
    path('<str:organization_id>/ddp/export', export_ddp, name='export'),
    path('<str:directory_name>/ddp/download', download_ddp, name='download'),
]
