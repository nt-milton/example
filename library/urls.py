from django.urls import path

from library.views import export_library_template

app_name = 'library'
urlpatterns = [
    path(
        'export/library_template',
        export_library_template,
        name='export_library_template',
    ),
]
