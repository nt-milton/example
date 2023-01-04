import json
import logging

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from laika.decorators import laika_service
from organization.models import Organization
from user.models import User
from user.scim.constants import USER_NOT_FOUND_ERROR
from user.scim.decorators import scim_request
from user.scim.helpers import (
    create_user_from_request,
    generate_user_body,
    patch_user_from_request,
    update_user_from_request,
)

logger = logging.getLogger('scim')


INTERNAL_ERROR = 'An internal error happened.'


def get_user(request: HttpRequest, user_id: str) -> HttpResponse:
    try:
        user = User.objects.get(
            username=user_id, organization__id=request.user.organization_id
        )
        return JsonResponse(generate_user_body(user))
    except User.DoesNotExist:
        return HttpResponseNotFound(USER_NOT_FOUND_ERROR, 'application/json')
    except Exception as e:
        logger.warning(f'Error when getting scim user: {e}')
        return HttpResponseServerError(INTERNAL_ERROR)


@scim_request
def update_user(request: HttpRequest, user_id: str) -> HttpResponse:
    try:
        body = json.loads(request.body)
        user = User.objects.get(username=user_id)
        user = update_user_from_request(body, user)
        user.save()
        return JsonResponse(generate_user_body(user))
    except Exception as e:
        logger.warning(f'Error updating scim user: {e}')
        return HttpResponseServerError(INTERNAL_ERROR)


@scim_request
def patch_user(request: HttpRequest, user_id: str) -> HttpResponse:
    try:
        body = json.loads(request.body)
        user = User.objects.get(username=user_id)
        user = patch_user_from_request(body, user)
        user.save()
        return JsonResponse(generate_user_body(user))
    except Exception as e:
        logger.warning(f'Error patching scim user: {e}')
        return HttpResponseServerError(INTERNAL_ERROR)


@csrf_exempt
@laika_service(permission='user.add_user', exception_msg='Cannot handle SCIM operation')
@require_http_methods(['GET', 'PUT', 'PATCH'])
def handle_users(request: HttpRequest, user_id: str) -> HttpResponse:
    if request.method == 'GET':
        return get_user(request, user_id)
    elif request.method == 'PUT':
        return update_user(request, user_id)
    elif request.method == 'PATCH':
        return patch_user(request, user_id)


@csrf_exempt
@laika_service(permission='user.add_user', exception_msg='Cannot create user')
@require_POST
@scim_request
def create_user(request: HttpRequest):
    try:
        body = json.loads(request.body)
        organization = Organization.objects.get(id=request.user.organization_id)
        user = create_user_from_request(body, organization)
        user.save()
        return JsonResponse(generate_user_body(user))
    except ValueError as e:
        logger.warning(f'Invalid scim request: {e}')
        return HttpResponseBadRequest('Invalid request')
    except Exception as e:
        logger.warning(f'Error creating scim user: {e}')
        return HttpResponseServerError(INTERNAL_ERROR)
