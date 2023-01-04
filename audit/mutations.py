import base64
import io
import logging
from datetime import datetime

import graphene
from django.core.files import File
from django.db.models import Q

from alert.constants import ALERT_TYPES
from audit.sections_factory.sections_factory_client import SectionFactoryClient
from audit.tasks import link_evidence_to_tags
from audit.types import AuditAuditorType, AuditType
from feature.models import AuditorFlag
from laika.aws.cognito import get_user
from laika.decorators import audit_service, laika_service
from laika.utils.dates import MM_DD_YYYY as DATE_TIME_FORMAT
from laika.utils.exceptions import ServiceException
from laika.utils.get_attr_type import (
    get_type_from_attribute,
    is_boolean_field,
    is_datetime_field,
    is_file_field,
    is_text_field,
)
from user.constants import AUDITOR_ADMIN
from user.helpers import create_auditor_credentials
from user.models import Auditor, User
from user.mutations import update_cognito_user
from user.permissions import change_user_permissions_group

from .constants import (
    AUDIT_FRAMEWORK_TYPES,
    AUDIT_STATUS_STEPS_FIELDS,
    CURRENT_AUDIT_STATUS,
    LEAD_AUDITOR_KEY,
)
from .inputs import (
    AssignAuditToAuditorInput,
    CheckStatusFieldInput,
    CreateAuditInput,
    CreateAuditUserInput,
    RemoveAuditorFromAuditInput,
    UpdateAuditDetailsInput,
    UpdateAuditorRoleInAuditTeamInput,
    UpdateAuditorStepInput,
    UpdateAuditorUserPreferencesInput,
    UpdateAuditStageInput,
    UpdateAuditUserInput,
)
from .models import (
    Audit,
    AuditAuditor,
    AuditFrameworkType,
    AuditStatus,
    AuditStepTimestamp,
    OrganizationAuditFirm,
)
from .utils.audit import (
    check_if_stage_can_be_enable,
    get_current_status,
    get_framework_key_by_value,
    get_role_to_assign,
)
from .utils.auditor_alerts import audit_stage_is_completed
from .utils.docusign import generate_docusign_fields

logger = logging.getLogger(__name__)


class CreateAudit(graphene.Mutation):
    class Arguments:
        input = CreateAuditInput(required=True)

    id = graphene.String()

    @laika_service(
        permission='audit.add_audit',
        exception_msg='Failed to created audit. Please try again',
        revision_name='Create audit',
    )
    def mutate(self, info, **kwargs):
        if (
            not kwargs['input'].get('audit_type')
            in dict(AUDIT_FRAMEWORK_TYPES).values()
        ):
            raise ServiceException('Audit type not supported!')

        organization = info.context.user.organization
        firm_name = kwargs['input'].get('audit_firm_name')
        org_audit_firm = OrganizationAuditFirm.objects.filter(
            audit_firm__name=firm_name,
        ).first()

        framework_type_key = get_framework_key_by_value(
            kwargs['input'].get('audit_type')
        )
        framework = AuditFrameworkType.objects.get(audit_type=framework_type_key)

        audit = kwargs['input'].to_model(
            organization=organization,
            audit_firm=org_audit_firm.audit_firm,
            audit_framework_type=framework,
        )
        docusign_fields = generate_docusign_fields(user=info.context.user, audit=audit)
        audit_status = AuditStatus.objects.create(
            audit=audit,
            requested=True,
            **docusign_fields,
        )

        section_factory = SectionFactoryClient(audit=audit)
        report_sections = section_factory.generate_all_sections()
        audit.add_section_files(sections=report_sections)

        report_v2_flag = AuditorFlag.objects.get(
            name='draftReportV2FeatureFlag',
            audit_firm=audit.audit_firm,
        )

        audit.use_new_version = report_v2_flag.is_enabled
        audit.save()

        auditor_admins = Auditor.objects.filter(user__role=AUDITOR_ADMIN).filter(
            Q(audit_firms__name=firm_name)
        )
        for auditor in auditor_admins:
            alert = audit_status.create_auditor_alert(
                sender=info.context.user,
                receiver=auditor.user,
                alert_type=ALERT_TYPES['ORG_REQUESTED_AUDIT'],
            )
            alert.send_auditor_alert_email(audit_status)

        link_evidence_to_tags.delay(organization.id)
        return CreateAudit(id=audit.id)


class CheckAuditStatusField(graphene.Mutation):
    class Arguments:
        input = CheckStatusFieldInput(required=True)

    id = graphene.String()

    @laika_service(
        permission='audit.change_audit',
        exception_msg='Failed to update audit status field.',
        revision_name='Update audit status field',
    )
    def mutate(self, info, input):
        audit_status_id = input.status_id
        audit_id = input.audit_id
        field = input.field

        audit_status = AuditStatus.objects.get(id=audit_status_id, audit_id=audit_id)
        if (
            field == AUDIT_STATUS_STEPS_FIELDS['DRAFT_REPORT_CHECKED']
            and not audit_status.review_draft_report_checked
        ):
            audit_status.draft_report_checked_timestamp = datetime.now()

        field_value = audit_status.__dict__[field]
        audit_status.__setattr__(field, not field_value)

        audit_status.save()

        if audit_stage_is_completed(audit_status):
            current_status = get_current_status(audit_status)
            if current_status == CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']:
                alert_type = ALERT_TYPES['ORG_COMPLETED_DRAFT_REPORT']

            elif current_status == CURRENT_AUDIT_STATUS['INITIATED']:
                alert_type = ALERT_TYPES['ORG_COMPLETED_INITIATION']

            audit = audit_status.audit
            auditors_query = Q(audit_team__audit=audit) | Q(user__role=AUDITOR_ADMIN)
            auditors = (
                Auditor.objects.filter(auditors_query)
                .filter(Q(audit_firms__name=audit.audit_firm.name))
                .distinct()
            )

            for auditor in auditors:
                alert = audit_status.create_auditor_alert(
                    sender=info.context.user,
                    receiver=auditor.user,
                    alert_type=alert_type,
                )
                alert.send_auditor_alert_email(audit_status)
        return CheckAuditStatusField(id=audit_status.id)


class UpdateAuditStage(graphene.Mutation):
    class Arguments:
        input = UpdateAuditStageInput(required=True)

    id = graphene.String()

    @laika_service(
        permission='audit.change_audit',
        exception_msg='Failed to move audit to next stage.',
        revision_name='Move audit to next stage',
    )
    def mutate(self, info, input):
        audit_status_id = input.id
        enable_stage = input.enable_stage

        audit_status = AuditStatus.objects.get(id=audit_status_id)

        check_if_stage_can_be_enable(
            audit_status=audit_status, enable_stage=enable_stage
        )

        field_to_update = enable_stage.lower()
        setattr(audit_status, field_to_update, True)
        setattr(audit_status, f'{field_to_update}_created_at', datetime.now())

        audit_status.save()
        alerts = audit_status.create_audit_stage_alerts()
        for alert in alerts:
            alert.send_audit_alert_email(audit_status)

        return UpdateAuditStage(id=audit_status.id)


class AuditorUpdateAuditStage(graphene.Mutation):
    class Arguments:
        input = UpdateAuditStageInput(required=True)

    id = graphene.String()

    @audit_service(
        permission='audit.change_audit',
        exception_msg='Failed to move audit to next stage.',
        revision_name='Move audit to next stage',
    )
    def mutate(self, info, input):
        enable_stage = input.enable_stage

        audit_status = AuditStatus.objects.get(id=input.id)

        check_if_stage_can_be_enable(
            audit_status=audit_status, enable_stage=enable_stage
        )

        field_to_update = enable_stage.lower()
        setattr(audit_status, field_to_update, True)
        if field_to_update == CURRENT_AUDIT_STATUS['COMPLETED']:
            audit_status.audit.completed_at = datetime.now()
            audit_status.audit.save()
        elif not getattr(audit_status, f'{field_to_update}_created_at'):
            setattr(audit_status, f'{field_to_update}_created_at', datetime.now())

        audit_status.save()
        alerts = audit_status.create_audit_stage_alerts()
        for alert in alerts:
            alert.send_audit_alert_email(audit_status)

        return AuditorUpdateAuditStage(id=audit_status.id)


class UpdateAuditorAuditDetails(graphene.Mutation):
    class Arguments:
        input = UpdateAuditDetailsInput(required=True)

    updated = graphene.Field(AuditType)

    @audit_service(
        permission='audit.change_audit',
        exception_msg='Failed to update audit details.',
        revision_name='Update audit details',
    )
    def mutate(self, info, input):
        audit_id = input.audit_id
        name = input.name
        audit_configuration = input.audit_configuration
        legal_name = input.legal_name
        short_name = input.short_name
        system_name = input.system_name

        audit = Audit.objects.get(id=audit_id)
        audit.name = name
        audit.audit_configuration = audit_configuration
        audit.organization.legal_name = legal_name
        audit.organization.name = short_name
        audit.organization.system_name = system_name
        audit.organization.save(update_fields=['name', 'legal_name', 'system_name'])
        audit.save(update_fields=['name', 'audit_configuration'])
        return UpdateAuditorAuditDetails(updated=audit)


class UpdateAuditorStep(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorStepInput(required=True)

    id = graphene.String()

    @laika_service(
        permission='audit.change_audit',
        exception_msg='Failed to update audit step.',
        revision_name='Update audit step',
    )
    def mutate(self, info, input):
        status_id = input.status_id
        field = input.field
        value = input.value

        audit_status = AuditStatus.objects.get(id=status_id)
        attr_type = get_type_from_attribute(model=audit_status, attr_name=field)
        if is_boolean_field(attr_type):
            setattr(audit_status, field, True)
        elif is_text_field(attr_type):
            setattr(audit_status, field, value)
        elif is_file_field(attr_type):
            file_name = input.file_name
            doc = File(name=file_name, file=io.BytesIO(base64.b64decode(value)))
            setattr(audit_status, field, doc)

        setattr(audit_status, f'{field}_updated_at', datetime.now())
        audit_status.save()
        return UpdateAuditorStep(id=audit_status.id)


class AuditorUpdateAuditContentStep(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorStepInput(required=True)

    id = graphene.String()

    @audit_service(
        permission='audit.change_audit',
        exception_msg='Failed to update audit step.',
        revision_name='Update audit step',
    )
    def mutate(self, info, input):
        field = input.field
        value = input.value
        audit_id = input.audit_id

        audit_status = AuditStatus.objects.get(id=input.status_id, audit_id=audit_id)

        attr_type = get_type_from_attribute(model=audit_status, attr_name=field)
        if is_boolean_field(attr_type):
            audit_status.track_steps_metrics(field)
            setattr(audit_status, field, True)
        elif is_text_field(attr_type):
            setattr(audit_status, field, value)
        elif is_file_field(attr_type):
            file_name = input.file_name
            doc = File(name=file_name, file=io.BytesIO(base64.b64decode(value)))
            setattr(audit_status, field, doc)
            if field == 'draft_report':
                audit_status.draft_report_name = file_name
        elif is_datetime_field(attr_type):
            setattr(audit_status, field, datetime.strptime(value, DATE_TIME_FORMAT))

        updated_at = datetime.now()
        updated_field = f'{field}_updated_at'

        setattr(audit_status, updated_field, updated_at)

        AuditStepTimestamp.objects.custom_create(
            updated_step=field, updated_at=updated_at, audit_status=audit_status
        )
        audit_status.save()
        return AuditorUpdateAuditContentStep(id=audit_status.id)


class AssignAuditToAuditor(graphene.Mutation):
    class Arguments:
        input = AssignAuditToAuditorInput(required=True)

    audit_id = graphene.String()

    @audit_service(
        permission='audit.assign_audit',
        exception_msg='Failed to assign audit to auditor.',
        revision_name='Add member to audit team',
    )
    def mutate(self, info, input):
        audit_id = input.audit_id
        auditor_emails = input.auditor_emails
        audit = Audit.objects.get(id=audit_id)
        role_to_assign = get_role_to_assign(input.role)

        if len(auditor_emails) > 1 and role_to_assign == LEAD_AUDITOR_KEY:
            raise ServiceException(
                'You can only assign one Lead Auditor to your team. Please try again.'
            )

        auditors_team = AuditAuditor.objects.filter(audit=audit)
        titles = [auditor.title_role for auditor in auditors_team]
        if (
            any(LEAD_AUDITOR_KEY in title for title in titles)
            and role_to_assign == LEAD_AUDITOR_KEY
        ):
            raise ServiceException(
                'Lead Auditor role already exist in the '
                'team. Please select another role.'
            )

        auditor_for_audit_exists = auditors_team.filter(
            auditor__user__email__in=auditor_emails
        ).exists()
        if auditor_for_audit_exists:
            raise ServiceException('Audit already is assigned to a given auditor.')

        for email in auditor_emails:
            auditor = Auditor.objects.get(user__email=email)
            audit_auditor = AuditAuditor(
                audit=audit, auditor=auditor, title_role=role_to_assign
            )
            audit_auditor.save()
        return AssignAuditToAuditor(audit_id=audit.id)


class UpdateAuditorRoleInAuditTeam(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorRoleInAuditTeamInput(required=True)

    audit_auditor = graphene.Field(AuditAuditorType)

    @audit_service(
        permission='audit.assign_audit',
        exception_msg='Failed to update auditor role in audit team.',
        revision_name='Edit auditor role in the audit team',
    )
    def mutate(self, info, input):
        audit_id = input.audit_id
        auditor_email = input.auditor_email
        audit = Audit.objects.get(id=audit_id)
        role_to_assign = get_role_to_assign(input.role)

        auditors_team = AuditAuditor.objects.filter(audit=audit)
        does_other_lead_auditor_exists_in_audit_team = any(
            LEAD_AUDITOR_KEY in auditor.title_role
            and auditor.auditor.user.email != auditor_email
            for auditor in auditors_team
        )

        if (
            does_other_lead_auditor_exists_in_audit_team
            and role_to_assign == LEAD_AUDITOR_KEY
        ):
            raise ServiceException(
                'Lead Auditor role already exist in the '
                'team. Please select another role.'
            )
        audit_auditor = auditors_team.get(auditor__user__email=auditor_email)
        audit_auditor.title_role = role_to_assign
        audit_auditor.save()
        return UpdateAuditorRoleInAuditTeam(audit_auditor=audit_auditor)


class RemoveAuditorFromAudit(graphene.Mutation):
    class Arguments:
        input = RemoveAuditorFromAuditInput(required=True)

    audit_id = graphene.String()

    @audit_service(
        permission='audit.assign_audit',
        exception_msg='Failed to remove auditor from audit.',
        revision_name='Remove member from audit team',
    )
    def mutate(self, info, input):
        audit_id = input.audit_id
        auditor_email = input.auditor_email
        AuditAuditor.objects.get(
            audit_id=audit_id, auditor__user__email=auditor_email
        ).delete()

        return RemoveAuditorFromAudit(audit_id)


class CreateAuditUser(graphene.Mutation):
    class Arguments:
        input = CreateAuditUserInput(required=True)

    created = graphene.Int()

    @audit_service(
        permission='audit.add_audit_user',
        exception_msg='Failed to invite audit user',
        revision_name='Create audit user',
    )
    def mutate(self, info, **kwargs):
        current_user = info.context.user
        audit_user_input = kwargs['input']
        email = audit_user_input.get('email')

        auditor_exists = Auditor.objects.filter(user__email=email).exists()

        if auditor_exists:
            raise ServiceException('Auditor already exists')

        user_data = {
            'first_name': audit_user_input.get('first_name'),
            'last_name': audit_user_input.get('last_name'),
            'email': email,
            'role': audit_user_input.get('permission'),
        }

        user = User.objects.create(**user_data, username=email)

        auditor = Auditor(user=user)
        auditor.save(is_not_django=True)

        auditor.audit_firms.set(current_user.auditor.audit_firms.all())

        create_auditor_credentials(
            {
                **user_data,
                'permission': user.role,
                'audit_firm': auditor.audit_firms.first().name,
            },
            sender=current_user.get_full_name().title(),
        )

        return CreateAuditUser(created=user.id)


class DeleteAuditUsers(graphene.Mutation):
    class Arguments:
        input = graphene.List(graphene.String, required=True)

    deleted = graphene.List(graphene.String)

    @audit_service(
        permission='audit.delete_audit_user',
        exception_msg='Failed to delete audit users',
        revision_name='Delete audit users',
    )
    def mutate(self, info, **kwargs):
        auditor_emails = kwargs['input']
        Auditor.objects.filter(user__email__in=auditor_emails).delete()

        User.objects.filter(
            email__in=auditor_emails,
        ).delete()

        return DeleteAuditUsers(deleted=auditor_emails)


class UpdateAuditUser(graphene.Mutation):
    class Arguments:
        input = UpdateAuditUserInput(required=True)

    updated = graphene.String()

    @audit_service(
        permission='audit.change_audit_user',
        exception_msg='Failed to update audit user',
        revision_name='Update audit user',
    )
    def mutate(self, info, **kwargs):
        input = kwargs.get('input')
        auditor_email = input.get('email')
        new_role = input.get('role')

        auditor_user = User.objects.get(email=auditor_email)

        old_role = auditor_user.role

        for attribute_name, attribute_value in input.items():
            setattr(auditor_user, attribute_name, attribute_value)
        auditor_user.save()

        should_update_role = old_role.lower() != new_role.lower()
        if should_update_role and auditor_user.is_active:
            change_user_permissions_group(old_role, new_role, auditor_user)

        if get_user(auditor_user.email):
            logger.info('Updating cognito user')
            update_cognito_user(auditor_user, input, new_role, old_role)

        return UpdateAuditUser(updated=auditor_email)


class UpdateAuditorUserPreferences(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorUserPreferencesInput(required=True)

    preferences = graphene.JSONString()

    @audit_service(
        permission='audit.update_audit_user_preferences',
        exception_msg='Failed to update audit user preferences',
        revision_name='Update audit user preferences',
    )
    def mutate(self, info, **kwargs):
        params = kwargs.get('input')
        auditor_email = params.get('email')
        preferences = params.get('user_preferences')

        auditor_user = User.objects.get(email=auditor_email)
        auditor_user.user_preferences = preferences
        auditor_user.save()

        return UpdateAuditorUserPreferences(preferences=preferences)
