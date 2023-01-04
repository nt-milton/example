import logging

import requests
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from laika.utils.exceptions import ServiceException
from link.models import Link

logger = logging.getLogger('link_utils')
REQUEST_TIMEOUT = 12  # Seconds


@csrf_exempt
def proxy_url_request(
    request,
    link_id,
    http_client=requests,
):
    try:
        logger.info(f'Requested link: {link_id}')
        if not link_id:
            logger.warning('Not link id in the request')
            return _invalid_link_response(request)

        link = Link.objects.get(id=link_id)

        if not link.is_valid:
            if link.is_expired:
                logger.warning(f'Link with id {link_id} is expired.')
                return render(
                    request,
                    'expired_link.html',
                    {'company_name': link.organization.name},
                )
            logger.warning(f'Link with id {link_id} is disabled.')
            return _invalid_link_response(request)

        try:
            if hasattr(link, 'report'):
                proxy_response = http_client.post(link.url, timeout=REQUEST_TIMEOUT)
            else:
                proxy_response = http_client.get(link.url, timeout=REQUEST_TIMEOUT)

            if proxy_response.status_code != 200:
                logger.warning(f'Error calling the internal url on link: {link}')
                return _invalid_link_response(request)

            content_type, content_disposition = _get_response_headers(proxy_response)

            response = HttpResponse(proxy_response.content, content_type=content_type)
            if content_disposition:
                response['Content-Disposition'] = content_disposition

            return response
        except requests.Timeout as err:
            logger.warning(
                f'Timeout error to open link with UUID {link_id}, error: {err}'
            )
            return _invalid_link_response(
                request,
                title='Your request timed out.',
                subtitle='Please wait a moment and try again.',
            )
    except (Link.DoesNotExist, ServiceException) as exc:
        logger.warning(f'Error to open link with UUID {link_id}, error: {exc}')
        return _invalid_link_response(request)


def _get_response_headers(proxy_response):
    content_type = None
    content_disposition = None
    try:
        has_headers = hasattr(proxy_response, 'headers')

        content_type = (
            proxy_response.headers['Content-Type']
            if has_headers
            else proxy_response['Content-Type']
        )

        content_disposition = (
            proxy_response.headers['Content-Disposition']
            if has_headers
            else proxy_response['Content-Disposition']
        )
    except KeyError as ke:
        logger.warning(f'Error getting header: {ke}')

    return content_type, content_disposition


def _invalid_link_response(
    request, title='This link is invalid!', subtitle='Please request a new link.'
):
    response = render(request, '404.html', {'title': title, 'subtitle': subtitle})
    response.status_code = 404
    return response
