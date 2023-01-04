from django.urls import path

from .views import export_training_exception_report, export_training_log

app_name = 'training'
urlpatterns = [
    path('<int:training_id>/log', export_training_log, name='export_training_log'),
    path(
        'training_exception_report',
        export_training_exception_report,
        name='training_exception_report',
    ),
]
