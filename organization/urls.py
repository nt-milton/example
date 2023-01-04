from django.urls import path

from .views import webhook_salesforce

app_name = 'organization'
urlpatterns = [path('salesforce', webhook_salesforce, name='webhook-salesforce')]
