from django.urls import path

from objects.views import export_laika_object, export_template

app_name = 'objects'
urlpatterns = [
    path('export', export_laika_object, name='export_laika_object'),
    path('export/template', export_template, name='export_template'),
]
