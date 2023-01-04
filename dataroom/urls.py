from django.urls import path

from .views import export_dataroom

app_name = 'dataroom'
urlpatterns = [
    path('<str:dataroom_id>/export-dataroom', export_dataroom, name='export-dataroom')
]
