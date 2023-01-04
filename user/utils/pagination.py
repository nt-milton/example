from laika.utils.paginator import get_paginated_result

DEFAULT_PAGE = 1
# Need to double check this value
DEFAULT_PAGE_SIZE = 50


def get_pagination_result(pagination, data):
    page = pagination.page if pagination.page else DEFAULT_PAGE
    page_size = pagination.page_size if pagination.page_size else DEFAULT_PAGE_SIZE

    return get_paginated_result(data, page_size, page)
