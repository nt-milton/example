from django.urls import path

from .views import export_drive

app_name = 'drive'
urlpatterns = [path('export', export_drive, name='export-drive')]
