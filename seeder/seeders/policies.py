import logging
from typing import Optional, Tuple

from django.core.files import File

from control.models import ControlPillar
from policy.constants import COMPLIANCE_RELEASE_DATE
from policy.models import Policy, PolicyTag, PublishedPolicy
from seeder.seeders.commons import are_columns_empty, get_formatted_tags, get_headers
from tag.models import Tag
from user.helpers import get_or_create_user_by_email

from .docx_templates import replace_placeholders

logger = logging.getLogger('seeder')


POLICIES = 'policies'

POLICY_FIELDS = [
    'name',
    'category',
    'description',
    'owner',
    'approver',
    'administrator',
]


def validate_fields(status_detail, dictionary):
    name = dictionary.get('name')
    description = dictionary.get('description')
    category = dictionary.get('category')

    if not name or not category or not description:
        status_detail.append(
            f'Error seeding policy with name: {name}, '
            f'category: {category}, description: {description}.'
            'All fields are required.'
        )
        return False

    is_published = dictionary.get('is_published')
    published_by = dictionary.get('published_by')

    if is_published and not published_by:
        status_detail.append(
            f'Error seeding policy with name: {name}. To publish '
            'the policy the field published_by is required.'
        )
        return False

    return True


def should_update(seeding_multiple, policy, dictionary):
    return (
        seeding_multiple
        and policy.created_at >= COMPLIANCE_RELEASE_DATE
        and policy.name == dictionary.get('name')
        and not policy.is_draft_edited
    )


def get_control_family_and_policy_type(
    dictionary,
) -> Tuple[Optional[ControlPillar], str]:
    pillar_name = dictionary.get('pillar_name')

    control_family = (
        ControlPillar.objects.filter(name=pillar_name).first() if pillar_name else None
    )

    policy_type = dictionary.get('policy_type')

    if policy_type not in ['Policy', 'Procedure']:
        policy_type = 'Policy'

    return control_family, policy_type


def create_policy(organization, dictionary) -> Tuple[Policy, bool]:
    control_family, policy_type = get_control_family_and_policy_type(dictionary)

    return Policy.objects.get_or_create(
        organization=organization,
        name=dictionary.get('name'),
        defaults={
            'category': dictionary.get('category'),
            'description': dictionary.get('description'),
            'control_family': control_family,
            'is_published': dictionary.get('is_published') or False,
            'policy_type': policy_type,
            'owner': get_or_create_user_by_email(
                dictionary.get('owner'), organization.id
            ),
            'administrator': get_or_create_user_by_email(
                dictionary.get('administrator'), organization.id
            ),
            'approver': get_or_create_user_by_email(
                dictionary.get('approver'), organization.id
            ),
        },
    )


def update_policy(organization, dictionary) -> Tuple[Policy, bool]:
    (control_family, _) = get_control_family_and_policy_type(dictionary)

    return Policy.objects.update_or_create(
        organization=organization,
        name=dictionary.get('name'),
        defaults={
            'category': dictionary.get('category'),
            'description': dictionary.get('description'),
            'control_family': control_family,
        },
    )


def upsert_policy(organization, dictionary, seeding_multiple):
    policy = get_policy(organization, dictionary)
    should_upsert = False
    created = False

    if policy:
        should_upsert = should_update(
            seeding_multiple,
            policy,
            dictionary,
        )
        if should_upsert:
            policy, created = update_policy(organization, dictionary)
    else:
        policy, created = create_policy(organization, dictionary)

    return (policy, created, should_upsert)


def __organization_placeholders(organization):
    org_placeholders = {'COMPANY_NAME': organization.name}
    if organization.logo:
        org_placeholders['COMPANY_LOGO'] = organization.logo.file
    return org_placeholders


def create_draft_file(organization, zip_obj, name):
    org_placeholders = __organization_placeholders(organization)
    try:
        policy_file = zip_obj.open(f'policies/{name}.docx')
    except Exception as e:
        logger.warning(
            'Error trying to open policy template for organization: '
            f'{organization.id} '
            f'Trace: {e}'
        )
        policy_file = open('policy/assets/empty.docx', 'rb')

    file_wp = replace_placeholders(policy_file, org_placeholders)

    return File(name=name + '.docx', file=file_wp) if file_wp else None


def upsert_draft(organization, policy, dictionary, created, should_upsert, zip_obj):
    if created or should_upsert:
        draft = create_draft_file(organization, zip_obj, dictionary.get('name'))

        if draft:
            policy.draft = draft
            policy.save()


def add_policy_tags(dictionary, policy, organization):
    if not dictionary.get('tags'):
        return

    for tag in get_formatted_tags(dictionary.get('tags')):
        created_tag, _ = Tag.objects.get_or_create(name=tag, organization=organization)

        PolicyTag.objects.update_or_create(policy=policy, tag=created_tag)


def upsert_tags(
    organization, policy, dictionary, created, should_upsert, seeding_multiple
):
    if should_upsert:
        policy.tags.set([])
        add_policy_tags(dictionary, policy, organization)

    if created or not seeding_multiple:
        add_policy_tags(dictionary, policy, organization)


def add_policy_publish(dictionary, policy, organization):
    if dictionary.get('is_published'):
        PublishedPolicy.objects.update_or_create(
            policy=policy,
            defaults={
                'published_by': get_or_create_user_by_email(
                    dictionary.get('published_by'), organization.id
                ),
                'contents': policy.draft,
                'comment': dictionary.get('published_comment')
                if dictionary.get('published_comment')
                else 'No comment',
            },
        )


def upsert_publish_policy(organization, policy, dictionary, created, seeding_multiple):
    if created or not seeding_multiple:
        add_policy_publish(dictionary, policy, organization)


def get_policy(organization, dictionary):
    return Policy.objects.filter(
        organization=organization,
        name=dictionary.get('name'),
    ).first()


def seed(organization, zip_obj, workbook, seeding_multiple=False):
    status_detail = []

    if 'policies' not in workbook.sheetnames:
        return status_detail

    headers = get_headers(workbook[POLICIES])
    for row in workbook[POLICIES].iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))

        if are_columns_empty(dictionary, POLICY_FIELDS):
            continue

        try:
            if not validate_fields(status_detail, dictionary):
                continue

            policy, created, should_upsert = upsert_policy(
                organization, dictionary, seeding_multiple
            )

            upsert_draft(
                organization,
                policy,
                dictionary,
                created,
                should_upsert,
                zip_obj,
            )

            upsert_tags(
                organization,
                policy,
                dictionary,
                created,
                should_upsert,
                seeding_multiple,
            )

            upsert_publish_policy(
                organization, policy, dictionary, created, seeding_multiple
            )
        except Exception as e:
            name = dictionary.get('name')
            logger.warning(f'Policy with name: {name} has failed. {e}')
            status_detail.append(f'Error seeding policy with name: {name}. Error: {e}')

    return status_detail
