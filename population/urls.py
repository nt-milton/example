from django.urls import path

from .views import (
    download_completeness_and_accuracy_file,
    download_population_file,
    export_population_template,
)

app_name = 'population'
urlpatterns = [
    path(
        'download-population-file',
        download_population_file,
        name='download-population-file',
    ),
    path(
        'export-population-template',
        export_population_template,
        name='export-population-template',
    ),
    path(
        'download-completeness-and-accuracy-file',
        download_completeness_and_accuracy_file,
        name='download-completeness-and-accuracy-file',
    ),
]
