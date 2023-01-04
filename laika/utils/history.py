import functools

import reversion


def create_revision(message):
    def create_revision_decorator(function):
        @functools.wraps(function)
        def decorator(*args, **kwargs):
            with reversion.create_revision(atomic=True):
                reversion.set_comment(message)
                return function(*args, **kwargs)

        return decorator

    return create_revision_decorator
