import base64
import io
import os

import graphene
from django.core.files.base import File
from docxtpl import DocxTemplate

from drive.models import DriveEvidence, DriveEvidenceData
from evidence.constants import FILE
from evidence.evidence_handler import get_files_to_upload
from feature.constants import new_controls_feature_flag
from laika.decorators import laika_service
from laika.utils.exceptions import ServiceException
from laika.utils.files import filename_has_extension
from policy.constants import (
    BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG,
    EMPTY_STRING,
    INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG,
)
from tag.models import Tag
from user.models import User

from .helpers import validate_administrator_is_empty, validate_input
from .inputs import (
    OnboardingPolicyInput,
    ReplacePolicyInput,
    UpdateIsDraftEditedInput,
    UpdateNewPolicyInput,
)
from .models import OnboardingPolicy, Policy
from .schema import PolicyType
from .utils.utils import create_or_delete_action_items_by_policy


class UpdateOnboardingPolicy(graphene.Mutation):
    class Arguments:
        input = OnboardingPolicyInput(required=True)

    updated = graphene.Int()

    @staticmethod
    @laika_service(
        permission='organization.change_onboarding',
        exception_msg='Failed to update onbaording policy',
        revision_name='Update Onboarding Policy',
    )
    def mutate(root, info, **kwargs):
        organization = info.context.user.organization
        policy_input = kwargs.get('input')
        onboarding_policy = OnboardingPolicy.objects.get(
            id=policy_input.id,
            organization=organization,
        )
        use_laika_template = policy_input.get('use_laika_template')
        file = policy_input.get('file')

        if use_laika_template is not None:
            onboarding_policy.use_laika_template = use_laika_template

        files = get_files_to_upload([file])
        file = next(iter(files), None)
        if file:
            tag, _ = Tag.objects.get_or_create(
                organization=organization, name='Onboarding'
            )
            drive_evidence_data = DriveEvidenceData(type=FILE, file=file, tags=[tag])
            drive_evidence = DriveEvidence.objects.custom_create(
                organization=organization,
                owner=info.context.user,
                drive_evidence_data=drive_evidence_data,
            )
            onboarding_policy.file = drive_evidence.evidence

        onboarding_policy.save()

        return UpdateOnboardingPolicy(updated=onboarding_policy.id)


class ReplacePolicy(graphene.Mutation):
    class Arguments:
        input = ReplacePolicyInput(required=True)

    id = graphene.UUID()

    @staticmethod
    @laika_service(
        permission='policy.change_policy',
        exception_msg='Failed to replace policy draft',
        revision_name='Update Onboarding Policy',
    )
    def mutate(root, info, input=None):
        # TODO - remove ff when all customers are migrated
        # to the new policy details view (revamp version).
        new_controls_ff_exists = info.context.user.organization.is_flag_active(
            new_controls_feature_flag
        )

        policy = Policy.objects.get(
            id=input.id, organization=info.context.user.organization
        )

        policy.draft = File(
            name=input.draft.file_name,
            file=io.BytesIO(base64.b64decode(input.draft.file)),
        )

        if not filename_has_extension(os.path.basename(policy.draft.name)):
            raise ServiceException(INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG)

        # Validation to prevent the user uploading docx
        # files with missing XML metadata
        try:
            DocxTemplate(policy.draft)
        except Exception:
            raise ServiceException(BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG)

        if policy.is_published and (
            not policy.owner
            or (
                validate_administrator_is_empty(
                    policy.administrator, new_controls_ff_exists
                )
            )
            or not policy.approver
        ):
            raise ServiceException('MissingPolicyOAA')

        policy.save(generate_key=True)
        return ReplacePolicy(id=policy.id)


class UpdateIsDraftEdited(graphene.Mutation):
    class Arguments:
        input = UpdateIsDraftEditedInput(required=True)

    success = graphene.Boolean()

    @staticmethod
    @laika_service(
        permission='policy.change_policy',
        exception_msg='Failed to update is draft edited',
        revision_name='Update Draft Policy',
    )
    def mutate(root, info, input: UpdateIsDraftEditedInput):
        Policy.objects.filter(
            id=input.id, organization_id=info.context.user.organization.id
        ).update(is_draft_edited=True)

        return UpdateIsDraftEdited(success=True)


@validate_input
def update_user(*, input, policy, field, org_id):
    if input[field]:
        user = User.objects.get(email=input[field], organization_id=org_id)
        setattr(policy, field, user)
    else:
        setattr(policy, field, None)


@validate_input
def update_policy_fields(*, input, policy, field, org_id):
    field_type = Policy._meta.get_field(field).get_internal_type()
    policy_field = input[field]
    if policy_field or field_type == 'BooleanField':
        setattr(policy, field, policy_field)
    elif not policy_field and field_type == 'TextField':
        setattr(policy, field, EMPTY_STRING)


@validate_input
def update_tags(*, input, policy, field, org_id):
    tags = input[field] if input[field] is not None else []
    current_tags = set(policy.tags.all())
    new_tags = [
        Tag.objects.get_or_create(
            id=tag.get('id'),
            defaults={'name': tag.get('name'), 'organization_id': org_id},
        )
        for tag in tags
    ]
    new_tags = {tag for tag, _ in new_tags}
    tags_to_remove = current_tags - new_tags
    tags_to_add = new_tags - current_tags
    policy.tags.remove(*tags_to_remove)
    policy.tags.add(*tags_to_add)


class UpdateNewPolicy(graphene.Mutation):
    class Arguments:
        input = UpdateNewPolicyInput(required=True)

    policy = graphene.Field(PolicyType)

    @laika_service(
        permission='policy.change_policy',
        exception_msg='Failed to update the policy details',
    )
    def mutate(self, info, input):
        organization_id = info.context.user.organization_id
        policy_id = input.id
        policy = Policy.objects.get(pk=policy_id)
        update_functions_fields = [
            (update_user, ['owner', 'approver']),
            (update_tags, ['tags']),
            (
                update_policy_fields,
                ['name', 'description', 'is_required', 'is_visible_in_dataroom'],
            ),
        ]
        policy_data = dict(input=input, org_id=organization_id, policy=policy)

        for update_func, fields in update_functions_fields:
            for field in fields:
                update_func(field=field, **policy_data)

        if policy.is_published:
            create_or_delete_action_items_by_policy(policy)

        policy.save()

        return UpdateNewPolicy(policy)
