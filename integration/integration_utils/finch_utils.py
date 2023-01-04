import uuid


def verify_finch_request_id(headers):
    try:
        return uuid.UUID(str(headers.get('Finch-Request-Id')))
    except ValueError:
        return None
