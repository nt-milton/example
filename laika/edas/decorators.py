from django.db import transaction

from laika.edas.exceptions import EdaErrorException


class Edas:
    """
    Class that consolidate the decorators to use in EDAS.
    """

    @staticmethod
    def on_event(*, subscribed_to: str, atomic=True):
        """
        on_event(subscribed_to, atomic) -> method

        Tag each event processor method with the edapp event it's associated with.
        And define if the transaction inside it should be atomic or not.
        """

        def register(func):
            if not subscribed_to:
                raise EdaErrorException(
                    f'Provided event of type {type(subscribed_to)} '
                    'cannot be used to subscribe event listener '
                    f'{func.__module__}.{func.__name__}'
                )
            func._event_name = subscribed_to
            if atomic:
                return transaction.atomic(func)
            return func

        return register
