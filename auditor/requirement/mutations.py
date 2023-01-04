import logging
from datetime import datetime, timezone

import graphene
from django.db.models import Q

from audit.constants import TITLE_ROLES_DICT
from audit.models import Audit
from auditor.automated_testing.automated_testing import AutomatedTestingProcess
from auditor.inputs import (
    AddAuditorRequirementInput,
    AssignRequirementInput,
    AutomateRequirementTestInput,
    CreateRequirementTestInput,
    DeleteAuditorRequirementInput,
    UpdateAuditorRequirementInput,
    UpdateRequirementFieldInput,
    UpdateRequirementsStatusInput,
    UpdateRequirementTestInput,
)
from auditor.utils import (
    assign_requirement_user,
    get_next_display_id,
    increment_display_id,
    is_auditor_associated_to_audit_firm,
    update_requirements_status,
    validate_requirement_complete_status_change,
)
from fieldwork.constants import CHECKLIST_AUTOMATED_TESTING_SEPARATOR
from fieldwork.models import (
    Criteria,
    CriteriaRequirement,
    Evidence,
    Requirement,
    RequirementEvidence,
    Test,
)
from fieldwork.types import RequirementType, TestType
from laika.decorators import audit_service
from laika.utils.exceptions import ServiceException
from user.constants import AUDITOR_ADMIN

logger = logging.getLogger('auditor_requirement_mutation')


class AssignAuditorTesterRequirement(graphene.Mutation):
    class Arguments:
        input = AssignRequirementInput(required=True)

    requirement_ids = graphene.List(graphene.String)

    @audit_service(
        permission='fieldwork.change_requirement',
        exception_msg='Failed to assign tester to requirement.',
        revision_name='Assign tester to requirement',
    )
    def mutate(self, info, input):
        audit = Audit.objects.get(id=input.get('audit_id'))

        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException("Auditor can not assign tester requirement")
        updated_timestamp = datetime.now()
        requirements_updated = assign_requirement_user(
            input, TITLE_ROLES_DICT['Tester'], updated_timestamp
        )
        return AssignAuditorTesterRequirement(
            requirement_ids=[rq.id for rq in requirements_updated]
        )


class AssignAuditorReviewerRequirement(graphene.Mutation):
    class Arguments:
        input = AssignRequirementInput(required=True)

    requirement_ids = graphene.List(graphene.String)

    @audit_service(
        permission='fieldwork.change_requirement',
        exception_msg='Failed to assign reviewer to requirement.',
        revision_name='Assign reviewer to requirement',
    )
    def mutate(self, info, input):
        audit = Audit.objects.get(id=input.get('audit_id'))
        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException("Auditor can not assign reviewer requirements")
        updated_timestamp = datetime.now()

        requirements_updated = assign_requirement_user(
            input, TITLE_ROLES_DICT['Reviewer'], updated_timestamp
        )
        return AssignAuditorReviewerRequirement(
            requirement_ids=[rq.id for rq in requirements_updated]
        )


class DeleteAuditorRequirement(graphene.Mutation):
    class Arguments:
        input = DeleteAuditorRequirementInput(required=True)

    deleted = graphene.List(graphene.String)

    @audit_service(
        permission='fieldwork.delete_requirement',
        exception_msg='Failed to delete audit requirements',
        revision_name='Delete audit requirement',
    )
    def mutate(self, info, input):
        audit_requirement_ids = input.get('requirementIds')

        audit_id = input.get('auditId')

        audit_requirement_list = Requirement.objects.filter(
            id__in=audit_requirement_ids, audit_id=audit_id
        )

        new_requirement = []
        for requirement in audit_requirement_list:
            requirement.is_deleted = True
            new_requirement.append(requirement)

        Requirement.objects.bulk_update(new_requirement, ['is_deleted'])
        RequirementEvidence.objects.filter(
            requirement_id__in=audit_requirement_ids
        ).delete()
        return DeleteAuditorRequirement(deleted=audit_requirement_ids)


class UpdateAuditorRequirementField(graphene.Mutation):
    class Arguments:
        input = UpdateRequirementFieldInput(required=True)

    requirement = graphene.Field(RequirementType)

    @audit_service(
        permission='fieldwork.change_requirement',
        exception_msg='Failed to update requirement field.',
        revision_name='Update requirement field',
    )
    def mutate(self, info, input):
        requirement_id = input.get('requirement_id')
        audit_id = input.get('audit_id')
        field = input.get('field')
        value = input.get('value')
        user = info.context.user

        requirement_qs = Requirement.objects.filter(
            id=requirement_id, audit_id=audit_id
        )

        if not requirement_qs.exists():
            raise ServiceException('Requirement not found')

        requirement = requirement_qs.first()

        setattr(requirement, field, value)

        if field == 'description':
            requirement.last_edited_at = datetime.now()
            requirement.last_edited_by = user

        requirement.save()

        return UpdateAuditorRequirementField(requirement=requirement)


class UpdateAuditorRequirementsStatus(graphene.Mutation):
    class Arguments:
        input = UpdateRequirementsStatusInput(required=True)

    updated = graphene.List(graphene.String)

    @audit_service(
        permission='fieldwork.change_requirement',
        exception_msg='Failed to update requirements status.',
        revision_name='Update requirements status',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        requirement_ids = input.get('ids')
        status = input.get('status')
        user = info.context.user

        requirements = Requirement.objects.filter(
            id__in=requirement_ids, audit__id=audit_id
        )

        if status == 'completed':
            audit = Audit.objects.get(pk=audit_id)
            validate_requirement_complete_status_change(user, audit, requirement_ids)

        updated_requirements = update_requirements_status(requirements, status, user)
        Requirement.objects.bulk_update(
            updated_requirements, ['status', 'times_moved_back_to_open']
        )
        return UpdateAuditorRequirementsStatus(updated=input.get('ids'))


class CreateAuditorRequirementTest(graphene.Mutation):
    class Arguments:
        input = CreateRequirementTestInput(required=True)

    test = graphene.Field(TestType)

    @audit_service(
        permission='fieldwork.add_test',
        exception_msg='Failed to create new requirement test.',
        revision_name='Create requirement test',
    )
    def mutate(self, info, input):
        requirement_id = input.requirement_id
        audit_id = input.audit_id

        requirement = Requirement.objects.get(id=requirement_id, audit_id=audit_id)

        tests = Test.objects.filter(
            requirement__id=requirement_id, requirement__audit__id=audit_id
        )

        display_id = get_next_display_id(tests, 'Test')

        test = Test.objects.create(display_id=display_id, requirement=requirement)

        return CreateAuditorRequirementTest(test=test)


class UpdateAuditorRequirementTest(graphene.Mutation):
    class Arguments:
        input = UpdateRequirementTestInput(required=True)

    test_id = graphene.String()

    @audit_service(
        permission='fieldwork.change_test',
        exception_msg='Failed to update requirement test.',
        revision_name='Update requirement test',
    )
    def mutate(self, info, input):
        test_id = input.get('test_id')
        requirement_id = input.get('requirement_id')
        audit_id = input.get('audit_id')
        field = input.get('field')
        value = input.get('value')
        user = info.context.user

        test = Test.objects.get(
            id=test_id, requirement__id=requirement_id, requirement__audit__id=audit_id
        )

        if field == 'automated_checklist':
            checklist_html, *automated_test_html = str(value).split(
                CHECKLIST_AUTOMATED_TESTING_SEPARATOR
            )
            test.checklist = checklist_html
            test.automated_test_result = (
                automated_test_html[0] if automated_test_html else ''
            )

        else:
            setattr(test, field, value)

            if field == 'name':
                test.last_edited_at = datetime.now()
                test.last_edited_by = user

        test.save()

        return UpdateAuditorRequirementTest(test_id=test.id)


class DeleteAuditorRequirementTest(graphene.Mutation):
    class Arguments:
        test_id = graphene.ID(required=True)

    test = graphene.Field(TestType)

    @audit_service(
        permission='fieldwork.delete_test',
        exception_msg='Failed to delete requirement test.',
        revision_name='Delete requirement test',
    )
    def mutate(self, info, test_id):
        user_role = info.context.user.role
        if user_role != AUDITOR_ADMIN:
            raise ServiceException('Only auditor admin can delete tests')
        test = Test.objects.get(id=test_id)
        test.is_deleted = True
        test.save()
        return DeleteAuditorRequirementTest(test=test)


class AutomateAuditorRequirementTest(graphene.Mutation):
    class Arguments:
        input = AutomateRequirementTestInput(required=True)

    test = graphene.Field(TestType)

    @audit_service(
        permission='fieldwork.change_test',
        exception_msg='Failed to automate requirement test.',
        revision_name='Automate requirement test',
    )
    def mutate(self, info, input):
        test_id = input.test_id
        requirement_id = input.requirement_id
        audit_id = input.audit_id
        test = Test.objects.get(
            id=test_id, requirement_id=requirement_id, requirement__audit_id=audit_id
        )
        automated_testing_process = AutomatedTestingProcess(test)
        if not automated_testing_process.is_test_automatable():
            raise ServiceException('Test cannot be automated')

        new_test_run_html = automated_testing_process.generate_question_answers_html()
        test.automated_test_result_updated_at = datetime.now(timezone.utc)
        test.times_run_automate_test += 1
        if test.automated_test_result:
            test.automated_test_result = (
                f'{new_test_run_html}\n{test.automated_test_result}'
            )
        else:
            test.automated_test_result = new_test_run_html

        test.save(
            update_fields=[
                'automated_test_result',
                'automated_test_result_updated_at',
                'times_run_automate_test',
            ]
        )

        return AutomateAuditorRequirementTest(test=test)


class AddAuditorRequirement(graphene.Mutation):
    class Arguments:
        input = AddAuditorRequirementInput(required=True)

    requirement = graphene.Field(RequirementType)

    @audit_service(
        permission='fieldwork.add_requirement',
        exception_msg='Failed to add requirement',
        revision_name='Add auditor requirement',
    )
    def mutate(self, info, input):
        user = info.context.user
        audit_id = input.get('audit_id')
        name = input.get('name')
        language = input.get('language')
        related_evidence = input.get('related_evidence')
        related_criteria = input.get('related_criteria')

        logger.info(
            f'Auditor user {user.username} is creating a requirementin audit {audit_id}'
        )

        audit = Audit.objects.get(id=audit_id)

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor cannot create a requirement')

        requirement_evidence = Evidence.objects.filter(
            id__in=related_evidence, audit_id=audit_id
        )

        requirement_criteria = Criteria.objects.filter(
            Q(id__in=related_criteria) & (Q(audit_id=audit_id) | Q(audit_id=None))
        )

        if len(requirement_evidence) > 0 and len(requirement_criteria) > 0:
            new_display_id = increment_display_id(Requirement, audit_id, 'LCL')
            new_requirement = Requirement.objects.custom_create(
                display_id=new_display_id,
                audit_id=audit_id,
                evidence=requirement_evidence,
                name=name,
                description=language,
            )

            for rc in requirement_criteria:
                CriteriaRequirement.objects.create(
                    criteria=rc, requirement=new_requirement
                )

            return AddAuditorRequirement(requirement=new_requirement)
        else:
            raise ServiceException('Not able to create a requirement')


class UpdateAuditorRequirement(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorRequirementInput(required=True)

    requirement = graphene.Field(RequirementType)

    @audit_service(
        permission='fieldwork.change_requirement',
        exception_msg='Failed to update requirement',
        revision_name='Update auditor requirement',
    )
    def mutate(self, info, input):
        user = info.context.user
        audit_id = input.get('audit_id')
        requirement_id = input.get('requirement_id')
        name = input.get('name')
        language = input.get('language')
        related_evidence = input.get('related_evidence')
        related_criteria = input.get('related_criteria')

        logger.info(
            f'Auditor user {user.username} is trying to update'
            f'the requirement {requirement_id} in audit {audit_id}'
        )

        audit = Audit.objects.get(id=audit_id)

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor cannot update a requirement')

        requirement_evidence = Evidence.objects.filter(
            id__in=related_evidence, audit_id=audit_id
        )

        requirement_criteria = Criteria.objects.filter(
            Q(id__in=related_criteria) & (Q(audit_id=audit_id) | Q(audit_id=None))
        )

        if len(requirement_evidence) > 0 and len(requirement_criteria) > 0:
            requirement = Requirement.objects.get(id=requirement_id, audit_id=audit_id)
            requirement.name = name
            requirement.description = language
            requirement.evidence.set(requirement_evidence)
            CriteriaRequirement.objects.filter(requirement_id=requirement.id).delete()
            for rc in requirement_criteria:
                CriteriaRequirement.objects.create(criteria=rc, requirement=requirement)

            requirement.save()
            return AddAuditorRequirement(requirement=requirement)
        else:
            raise ServiceException('Not able to update the requirement')


class RequirementMutation(object):
    assign_auditor_tester_requirement = AssignAuditorTesterRequirement.Field()
    assign_auditor_reviewer_requirement = AssignAuditorReviewerRequirement.Field()
    delete_auditor_requirement = DeleteAuditorRequirement.Field()
    update_auditor_requirement_field = UpdateAuditorRequirementField.Field()
    update_auditor_requirements_status = UpdateAuditorRequirementsStatus.Field()
    create_auditor_requirement_test = CreateAuditorRequirementTest.Field()
    update_auditor_requirement_test = UpdateAuditorRequirementTest.Field()
    delete_auditor_requirement_test = DeleteAuditorRequirementTest.Field()
    create_auditor_requirement = AddAuditorRequirement.Field()
    update_auditor_requirement = UpdateAuditorRequirement.Field()
    automate_auditor_requirement_test = AutomateAuditorRequirementTest.Field()
