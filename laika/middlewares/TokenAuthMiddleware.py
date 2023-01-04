import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from laika.backends.base import decode_jwt_async
from user.models import User

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user(email: str):
    return User.objects.get(email=email)


class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope['user'] = AnonymousUser()

        query_string = scope['query_string']
        email = ''
        if query_string:
            try:
                # TODO: Authenticate Token by backends
                jwt = parse_qs(query_string)[b'token'][0].decode()
                logger.info('⚡️ Trying to connect Web Socket...')

                decoded_token = await decode_jwt_async(jwt)
                email = decoded_token.get('email', '')
                if email:
                    scope['user'] = await get_user(email)
            except Exception as exc:
                logger.warning(
                    f'Error on web socket authentication: {exc} with email: {email}'
                )

        return await self.inner(scope, receive, send)
