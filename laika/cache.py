import functools
import logging

from django.core.cache import cache

DEFAULT_TIME_OUT = 86400  # 24hrs

logger = logging.getLogger('cache')


def cache_func(func):
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        # This next 'if' is inserted to be able to called the
        # function under the decorator to ignore the
        # cache logic, so tests can work.
        if kwargs.get('no_cache', None):
            return func(*args, **kwargs)

        name = kwargs.get('cache_name')
        time_out = kwargs.get('time_out', DEFAULT_TIME_OUT)
        force_update = kwargs.get('force_update')
        cached_data = cache.get(name)

        if cached_data is None or force_update:
            cached_data = func(*args, **kwargs)
            cache.set(name, cached_data, time_out)
        if cached_data is None:
            logger.warning(f'No cached data exists for: {name}')

        return cached_data

    return decorator
