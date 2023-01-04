from django.urls import path

from .views import export_vendors

app_name = 'vendor'
urlpatterns = [path('export_vendors', export_vendors, name='export_vendors')]
