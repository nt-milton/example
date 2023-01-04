from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models.query import QuerySet

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50


def get_paginated_result(rows, page_size, page=1):
    p = Paginator(rows, page_size)
    try:
        page_obj = p.page(page)
    except PageNotAnInteger:
        page_obj = p.page(1)
    except EmptyPage:
        page_obj = p.page(p.num_pages)
    total = rows.count() if isinstance(rows, QuerySet) else len(rows)
    return {
        # TODO: Remove page when kogaio table is removed
        'page': page_obj.number,
        'current': page_obj.number,
        'pages': p.num_pages,
        'has_next': page_obj.has_next(),
        'has_prev': page_obj.has_previous(),
        'data': page_obj.object_list,
        'page_size': page_size,
        'total': total,
    }
