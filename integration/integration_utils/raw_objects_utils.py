# General utilities for integrations
import json
import logging

from integration.log_utils import time_metric

logger_name = __name__
logger = logging.getLogger(logger_name)

NULL_UNICODE = '\\u0000'
ESCAPE_CHARACTER = '\''


# Postgres doesn't support some set of unicodes.
def replace_unsupported_unicode(raw: dict) -> dict:
    with time_metric('replace_unsupported_unicode'):
        raw_str = json.dumps(raw)
        if NULL_UNICODE in raw_str or ESCAPE_CHARACTER in raw_str:
            replaced_raw = raw_str.replace(NULL_UNICODE, '').replace(
                ESCAPE_CHARACTER, '\\'
            )
            try:
                return json.loads(replaced_raw)
            except Exception as exc:
                message = f'{json} raised an exception {exc}'
                logger.info(message)

        return raw
