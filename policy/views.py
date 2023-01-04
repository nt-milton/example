import enum
import io
import json
import logging
import os

import requests
import reversion
from django.core.files import File
from django.http import JsonResponse
from django.http.response import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from feature.constants import new_controls_feature_flag
from laika.auth import login_required
from laika.utils.office import export_document_bytes
from laika.utils.pdf import merge, render_template_to_pdf
from policy.models import Policy
from user.models import User

logger = logging.getLogger('policy')


class DocumentStatus(enum.Enum):
    AUTO_SAVE = 2
    FORCE_SAVE = 6


def __get_callback_url(event):
    return event['url'].replace('/localhost/', '/document-server/')


def process_only_office_event(event):
    if (
        event['status'] == DocumentStatus.AUTO_SAVE.value
        or event['status'] == DocumentStatus.FORCE_SAVE.value
    ):
        response = requests.get(__get_callback_url(event), stream=True)
        response.raise_for_status()

        new_contents = response.raw.read()
        policy = Policy.objects.get(draft_key=event['key'])
        policy.draft = File(
            name=os.path.basename(policy.draft.name), file=io.BytesIO(new_contents)
        )
        with reversion.create_revision():
            reversion.set_comment('Updated policy')
            reversion.set_user(User.objects.get(username=event.get('users', [None])[0]))
        if event['status'] is DocumentStatus.AUTO_SAVE.value:
            policy.save(generate_key=True)
        else:
            policy.save()


@csrf_exempt
def save_document(request):
    event = json.loads(request.body)
    try:
        process_only_office_event(event)
        return JsonResponse({'error': 0})
    except Exception:
        logger.exception(f'Error processing OnlyOffice event {event}', exc_info=True)
        return JsonResponse({'error': 1})


def merge_policy_details_template(
    all_policies, published_policy_pdf, published_policy, organization
):
    # TODO - Remove this validation when all customers are migrated to MyCompliance
    my_compliance_enabled = organization.is_flag_active(new_controls_feature_flag)
    policy_details_pdf = render_template_to_pdf(
        template='policy/policy_details.html',
        context={
            'all_policies': all_policies,
            'policy': published_policy.policy,
            'published_policy': published_policy,
            'organization': organization,
            'administrator_enabled': not my_compliance_enabled,
        },
    )

    return merge(published_policy_pdf, policy_details_pdf)


@login_required
def export_policy_document(request, policy_id):
    return export_policy(policy_id, request.GET)


def export_policy(policy_id, query_params=None):
    if query_params is None:
        query_params = {}
    policy = Policy.objects.get(pk=policy_id)
    merged_pdf = get_published_policy_pdf(
        policy_id, query_params.get('published_policy_id')
    )
    response = HttpResponse(merged_pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment;filename="{policy.name}.pdf"'

    return response


def get_published_policy_pdf(policy_id, published_policy_id=None, for_download=True):
    """
    If the published_policy_id is not None, the data will be sent with the
    specific published policy. Otherwise, the data will be sent with the
    latest published policy.
    """

    policy = Policy.objects.get(pk=policy_id)
    if not published_policy_id:
        all_policies = policy.versions.all().order_by('-version')
        published_policy = all_policies.first()
    else:
        published_policy = policy.versions.get(id=published_policy_id)
        all_policies = None
    organization = policy.organization

    if not published_policy:
        logger.info(f'Published policy for policy {policy_id} is None')
        return None

    published_policy_pdf = export_document_bytes(
        published_policy.published_key,
        published_policy.policy.name,
        published_policy.contents.url,
    )

    if for_download:
        published_policy_pdf = merge_policy_details_template(
            all_policies, published_policy_pdf, published_policy, organization
        )

    return published_policy_pdf


@require_GET
@login_required
def published_policy_document(request, policy_id):
    return published_policy(policy_id, request.GET)


def published_policy(policy_id, query_params=None):
    if query_params is None:
        query_params = {}
    policy = Policy.objects.get(pk=policy_id)
    pdf_bytes = get_published_policy_pdf(
        policy_id, query_params.get('published_policy_id'), for_download=False
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment;filename="{policy.name}.pdf"'

    return response
