from django.urls import path

from .views import export_monitor, export_monitor_results

app_name = 'monitor'

urlpatterns = [
    path('export/result/report', export_monitor, name='export_report'),
    path(
        'export/results/<int:org_monitor_id>',
        export_monitor_results,
        name='export_monitor_results',
    ),
]
