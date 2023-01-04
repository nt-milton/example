from django_redis import get_redis_connection

from laika.settings import ENVIRONMENT


def get_redis_connection_from_pool() -> get_redis_connection:
    return get_redis_connection('redis' if ENVIRONMENT == 'local' else 'default')
