from django.conf import urls
from django.urls import path

from link import views

from .proxy import proxy_url_request

urlpatterns = [path('<uuid:link_id>/', proxy_url_request, name='Proxy the URL')]

urls.handler404 = views.error_404
