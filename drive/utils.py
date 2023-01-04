from django.core.cache import cache
from django.db.models import F

import evidence.constants as constants
from evidence.utils import tags_associated_to_evidence
from laika.cache import cache_func
from search.types import CmdKDriveResultType
from user.constants import CONCIERGE, ROLE_ADMIN, ROLE_MEMBER, ROLE_SUPER_ADMIN


def filter_templates_query(user):
    is_super_or_admin_or_contributor = user.role in [
        ROLE_SUPER_ADMIN,
        CONCIERGE,
        ROLE_MEMBER,
        ROLE_ADMIN,
    ]
    return {'is_template': False} if not is_super_or_admin_or_contributor else {}


@cache_func
def evidence_and_system_tags(evidence, **kwargs):
    return evidence.evidence_and_system_tags


def trigger_drive_cache(organization, evidence, action='CREATE'):
    # Updating document tags cache
    for e in evidence:
        eid = e if isinstance(e, str) else e.id
        cache_name = f'doc_tags_{organization.id}_{eid}'
        if action == 'CREATE':
            tags_associated_to_evidence(e, cache_name=cache_name, force_update=True)
        else:
            cache.delete(cache_name)

    # Updating the documents tags filter
    cache_name = f'tags_filter_{organization.id}'
    drive = organization.drive
    evidence_and_system_tags(drive.evidence, cache_name=cache_name, force_update=True)


def launchpad_mapper(model, organization_id):
    drive = model.objects.get(organization_id=organization_id)
    return [
        CmdKDriveResultType(
            id=document.document_id,
            description=document.description,
            name=document.name,
            url=f"/documents/{document.document_id}",
            text=document.evidence_text,
        )
        for document in drive.evidence.filter(
            evidence__type__in=(constants.LAIKA_PAPER, constants.FILE)
        ).annotate(
            name=F('evidence__name'),
            description=F('evidence__description'),
            evidence_text=F('evidence__evidence_text'),
            document_id=F('evidence__id'),
        )
    ]
