from log_request_id import local
from log_request_id.filters import RequestIDFilter

EMPTY_STRING = ''


class EdasSpanIdFilter(RequestIDFilter):
    def filter(self, record):
        record.span_id = getattr(local, 'span_id', EMPTY_STRING)
        super().filter(record)
        return True
