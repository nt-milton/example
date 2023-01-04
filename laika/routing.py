from django.urls import re_path

from alert.consumer import AlertWebConsumer

alerts_url = r'^ws/alert/(?P<room_id>[\w.@+-]+)/(?P<email>[\w.@+-]+)$'

websocket_urlpatterns = [re_path(alerts_url, AlertWebConsumer.as_asgi())]
