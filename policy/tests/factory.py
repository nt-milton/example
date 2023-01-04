from django.conf import settings
from django.core.files import File

from policy.docx_helper import remove_proposed_changes
from policy.models import Policy, PublishedPolicy

BASE_DIR = settings.BASE_DIR


def create_empty_policy(
    organization,
    user,
    name='Empty-test',
    category='Business Continuity & Disaster Recovery',
    **kwargs,
):
    empty_file = open(BASE_DIR + '/policy/assets/empty.docx', 'rb')
    doc = File(name=f'{name}.docx', file=empty_file)
    return Policy.objects.create(
        organization=organization,
        name=name,
        category=category,
        description='testing',
        administrator=user,
        approver=user,
        owner=user,
        draft=doc,
        **kwargs,
    )


def create_published_empty_policy(organization, user, **kwargs):
    policy = create_empty_policy(organization, user, **kwargs)
    PublishedPolicy.objects.create(
        published_by=user,
        owned_by=user,
        approved_by=user,
        policy=policy,
        contents=File(
            name=policy.draft.name,
            file=remove_proposed_changes(policy.draft, policy.id),
        ),
        comment='published',
    )
    return Policy.objects.get(organization=organization, id=policy.id)
