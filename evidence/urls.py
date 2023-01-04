from django.urls import path

from .views import export_evidence

app_name = 'evidence'
urlpatterns = [path('export', export_evidence, name='evidence')]
