"""
ASGI config for laika project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.core.asgi import get_asgi_application

from laika.middlewares.TokenAuthMiddleware import TokenAuthMiddleware
from laika.settings import ENVIRONMENT, ORIGIN, ORIGIN_LOCALHOST, UNDER_TEST

from .routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'laika.settings')


VALID_ORIGINS = ORIGIN_LOCALHOST if ENVIRONMENT == 'local' else ORIGIN


def token_auth_middleware_stack(inner):
    return TokenAuthMiddleware(AuthMiddlewareStack(inner))


application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        'websocket': OriginValidator(
            token_auth_middleware_stack(URLRouter(websocket_urlpatterns)),
            VALID_ORIGINS if not UNDER_TEST else ['*'],
        ),
    }
)
