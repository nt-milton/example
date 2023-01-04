from django.urls import path

from .views import oauth_callback, webhook_checkr

app_name = 'integration'
urlpatterns = [
    path('<str:vendor_name>/callback/', oauth_callback, name='oauth-callback'),
    path('checkr/incoming', webhook_checkr),
]
