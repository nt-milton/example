import logging
import re
from json import JSONDecodeError

from laika.utils.exceptions import ServiceException

logger = logging.getLogger('migrations')

SQL_KEY_ERRORS = ['column', 'of relation', 'does not exist']
MATCHING_QUERY_ERROR = 'matching query does not exist'
SKIP_EXCEPTIONS = (JSONDecodeError,)


class SQLErrorMiddleware:
    def on_error(self, error):
        skip_if = re.search(MATCHING_QUERY_ERROR, str(error)) or isinstance(
            error, SKIP_EXCEPTIONS
        )
        if bool(skip_if) is False:
            for key_error in SQL_KEY_ERRORS:
                if re.search(key_error, str(error)):
                    logger.error(error)
                    raise ServiceException(
                        'You have some unapplied migrations, go ahead and apply them'
                    )

        raise error

    def resolve(self, next, root, info, **args):
        return next(root, info, **args).catch(self.on_error)
