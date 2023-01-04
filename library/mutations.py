import logging

import graphene
from django.db import transaction

from dataroom.models import Dataroom
from dataroom.services.dataroom import DataroomService
from laika.constants import WSEventTypes
from laika.decorators import laika_service
from laika.utils.exceptions import ServiceException
from laika.utils.history import create_revision
from laika.utils.schema_builder.template_builder import TemplateBuilder
from laika.utils.websocket import send_message
from library.constants import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    LibraryTemplateSchema,
)
from library.inputs import (
    AddDocumentsQuestionnaireDataroomInput,
    BulkUpdateQuestionnaireStatusInput,
    CreateQuestionnaireQuestionInput,
    DeleteLibraryQuestionInput,
    DeleteQuestionnaireQuestionsInput,
    DeleteQuestionnairesInput,
    EquivalentQuestionInput,
    LibraryFileInput,
    ResolveEquivalentSuggestionInput,
    UpdateLibraryQuestionInput,
    UpdateLibraryQuestionStatusInput,
    UpdateQuestionAnswerInput,
    UpdateQuestionAssignedUserInput,
)
from library.models import LibraryEntry, LibraryTask, Question, Questionnaire
from library.services.question import QuestionService
from library.services.questionnaire import QuestionnaireService
from library.types import (
    LibraryBulkUploadType,
    NewQuestionnaireResponseType,
    QuestionType,
)
from library.utils import (
    get_question_by_id,
    notify_library_entry_answer_modification,
    update_library_question_status,
    update_questionnaire_status,
    update_questions_index_by_questionnaire,
)
from search.indexing.question_index import question_search_index
from user.helpers import get_user_by_email

from .tasks import create_library_equivalent_suggestions

logger = logging.getLogger(__name__)


class BulkLibraryUpload(graphene.Mutation):
    class Arguments:
        input = LibraryFileInput(required=True)

    upload_result = graphene.Field(LibraryBulkUploadType)

    @laika_service(
        atomic=False,
        permission='library.bulk_upload_library',
        exception_msg='Failed to upload library file. Please try again.',
    )
    def mutate(self, info, input):
        builder = TemplateBuilder(schemas=[LibraryTemplateSchema])
        data = builder.parse(input.library_file)
        library_results = data[LibraryTemplateSchema.sheet_name]

        if library_results.error:
            raise ServiceException(str(library_results.error))

        if library_results.failed_rows:
            return BulkLibraryUpload(
                upload_result=LibraryBulkUploadType(
                    failed_rows=builder.summarize_errors(library_results.failed_rows)
                )
            )

        if len(library_results.success_rows) == 0:
            raise ServiceException('No questions were added in the file')

        imported_questions = QuestionService.bulk_import(
            library_results.success_rows,
            organization_id=info.context.user.organization.id,
        )

        latest_id = Question.objects.latest('id').id
        library_task = LibraryTask.objects.create(created_by=info.context.user)

        create_library_equivalent_suggestions.apply_async(
            args=(
                latest_id,
                [question.id for question in imported_questions],
                info.context.user.id,
                library_task.id,
            ),
            countdown=5,
        )

        question_search_index.add_to_index(imported_questions, False, True)

        return BulkLibraryUpload(
            upload_result=LibraryBulkUploadType(success_rows=imported_questions)
        )


class CreateQuestionnaireEntry(graphene.Mutation):
    questionnaire = graphene.Field(NewQuestionnaireResponseType)

    class Arguments:
        name = graphene.String()

    @laika_service(
        permission='library.add_questionnaire',
        exception_msg='Failed to add new questionnaire',
        revision_name='Questionnaire created',
    )
    def mutate(self, info, name):
        organization = info.context.user.organization
        repeated_questionnaire = Questionnaire.objects.filter(
            name=name.strip(), organization=organization
        )

        if repeated_questionnaire.count():
            raise ServiceException(
                """
                This questionnaire name is already in use.
                Please enter a unique name.
                """
            )

        questionnaire = Questionnaire.objects.create(
            name=name.strip(), organization=organization
        )
        return CreateQuestionnaireEntry(questionnaire=questionnaire)


class BulkUpdateQuestionnaireStatus(graphene.Mutation):
    class Arguments:
        input = BulkUpdateQuestionnaireStatusInput(required=True)

    updated = graphene.List(graphene.String)

    @laika_service(
        permission='library.change_questionnaire',
        exception_msg='Failed to bulk update questionnaire status.',
        revision_name='Bulk update questionnaire status',
    )
    def mutate(self, info, input):
        questionnaire_ids = input.get('ids')
        questionnaires = Questionnaire.objects.filter(id__in=questionnaire_ids)
        new_status = input.get('status')

        if new_status not in [STATUS_IN_PROGRESS, STATUS_COMPLETED]:
            raise ServiceException('Invalid new status for questionnaire')

        updated_questionnaires = update_questionnaire_status(questionnaires, new_status)

        Questionnaire.objects.bulk_update(updated_questionnaires, ['completed'])

        for questionnaire_id in questionnaire_ids:
            update_questions_index_by_questionnaire(
                questionnaire_id, new_status == STATUS_COMPLETED
            )

        return BulkUpdateQuestionnaireStatus(updated=questionnaire_ids)


class DeleteQuestionnaire(graphene.Mutation):
    class Arguments:
        input = DeleteQuestionnairesInput(required=True)

    deleted = graphene.List(graphene.String)

    @laika_service(
        permission='library.change_questionnaire',
        exception_msg='Failed to delete questionnaire. Please try again.',
        revision_name='Delete Questionnaire',
    )
    def mutate(self, info, input):
        ids = input.ids
        delete_all = input.delete_all_questions
        organization = info.context.user.organization
        questionnaires = Questionnaire.objects.filter(id__in=input.get('ids'))

        if questionnaires.count() != len(ids):
            raise ServiceException('Invalid questionnaire(s) to delete')

        for id in ids:
            questionnaire_to_delete = Questionnaire.objects.filter(
                organization=organization, id=id
            ).first()
            if delete_all:
                questionnaire_questions = questionnaire_to_delete.questions.all()
                LibraryEntry.objects.filter(
                    question__in=questionnaire_questions
                ).delete()
                questionnaire_questions.hard_delete()
            questionnaire_to_delete.questions.clear()
            QuestionnaireService.delete_questionnaire_alerts(
                questionnaire=questionnaire_to_delete
            )
            questionnaire_to_delete.delete()
        return DeleteQuestionnaire(deleted=ids)


class CreateQuestionnaireQuestions(graphene.Mutation):
    questions = graphene.List(QuestionType)

    class Arguments:
        input = CreateQuestionnaireQuestionInput(required=True)

    @classmethod
    def restore_records(cls, questions, questionnaire: Questionnaire):
        soft_deleted_questions = Question.all_objects.filter(
            text__in=[question.text for question in questions],
            deleted_at__isnull=False,
            library_entry__organization=questionnaire.organization,
            questionnaires__in=[questionnaire],
        )
        for soft_deleted_question in soft_deleted_questions:
            soft_deleted_question.deleted_at = None
            soft_deleted_question.metadata = {}
        Question.all_objects.bulk_update(
            objs=soft_deleted_questions, fields=['deleted_at', 'metadata']
        )
        questionnaire.questions.add(*soft_deleted_questions)

    @classmethod
    def get_records(
        cls, questions, questionnaire: Questionnaire, overwrite_answer_addresses: bool
    ):
        updated_questions = []
        for question in questions:
            try:
                db_question = questionnaire.questions.get(
                    text=question.text,
                    library_entry__organization=questionnaire.organization,
                )

                metadata = {**db_question.metadata, **question.metadata}
                db_question.metadata = metadata
                db_question.save()
                QuestionService.reconcile_answer_when_creating_question(db_question)
            except Question.DoesNotExist:
                created_entry = LibraryEntry.objects.create(
                    organization=questionnaire.organization
                )
                db_question = Question.objects.create(
                    text=question.text,
                    metadata=question.metadata,
                    default=True,
                    library_entry=created_entry,
                )
            updated_questions.append(db_question)
        return updated_questions

    @laika_service(
        permission='library.change_libraryentry',
        exception_msg='Failed to add new question',
        revision_name='Questions created',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        questionnaire = Questionnaire.objects.get(
            id=input.get('questionnaire_id'),
            organization=organization,
        )
        if questionnaire.completed:
            raise ServiceException('Cannot modify a completed questionnaire')

        CreateQuestionnaireQuestions.restore_records(
            input.get('questions'), questionnaire
        )

        questions = CreateQuestionnaireQuestions.get_records(
            input.get('questions'),
            questionnaire,
            input.get('overwrite_answer_addresses'),
        )

        questionnaire.questions.add(*questions)
        send_message(info, WSEventTypes.LIBRARY_QUESTIONS_ADDED.value, logger=logger)
        question_search_index.add_to_index(questions, False, False)
        return CreateQuestionnaireQuestions(questions=questions)


class DeleteQuestionnaireQuestions(graphene.Mutation):
    class Arguments:
        input = DeleteQuestionnaireQuestionsInput(required=True)

    deleted_ids = graphene.List(graphene.String)
    updated = graphene.List(QuestionType)

    @laika_service(
        permission='library.delete_question',
        exception_msg='Failed to delete questionnaire question.' + ' Please try again.',
        revision_name='Delete Questionnaire Question',
    )
    def mutate(self, info, input):
        question_ids_deleted = []
        questions_updated = []
        organization = info.context.user.organization
        questionnaire_id = input.get('questionnaire_id')
        input_questions = input.get('questions')

        questionnaire = Questionnaire.objects.get(
            id=questionnaire_id,
            organization=organization,
        )
        if questionnaire.completed:
            raise ServiceException('Cannot modify a completed questionnaire')

        if not questionnaire:
            raise ServiceException('Invalid questionnaire to delete questions from it')

        questions_by_text = {}

        for question in input_questions:
            formulas = questions_by_text.get(question.text, [])
            questions_by_text[question.text] = formulas + question.formulas

        questions = questionnaire.questions.filter(
            text__in=[question.text for question in input_questions]
        )
        for question in questions:
            answer = question.metadata.get('answer', {})
            short_answer = question.metadata.get('shortAnswer', {})
            formulas = questions_by_text.get(question.text, [])
            new_meta = {**question.metadata}
            if short_answer.get('address') in formulas:
                new_meta['shortAnswer'] = {'address': '', 'options': []}
            if answer.get('address') in formulas:
                new_meta['answer'] = {'address': '', 'options': []}
            if (
                new_meta.get('answer', {}).get('address', '') == ''
                and new_meta.get('shortAnswer', {}).get('address', '') == ''
            ):
                question.delete()
                question_ids_deleted.append(question.id)
            else:
                questions_updated.append(question)
            question.metadata = {**question.metadata, **new_meta}
            question.save()

        send_message(info, WSEventTypes.LIBRARY_QUESTIONS_DELETED.value, logger=logger)
        return DeleteQuestionnaireQuestions(
            deleted_ids=question_ids_deleted, updated=questions_updated
        )


class UpdateQuestionAssignedUser(graphene.Mutation):
    class Arguments:
        input = UpdateQuestionAssignedUserInput(required=True)

    question = graphene.String()

    @laika_service(
        permission='library.change_question',
        exception_msg='Failed to assign user to question. Please try again.',
        revision_name='Assign User to Question',
    )
    def mutate(self, info, input: UpdateQuestionAssignedUserInput):
        organization_id = info.context.user.organization.id
        user_assigned = get_user_by_email(
            organization_id=organization_id, email=input.user_assigned_email
        )
        question = QuestionService.assign_user_to_question(
            organization_id=organization_id,
            question_id=input.question_id,
            user_assigned=user_assigned,
        )

        QuestionnaireService.generate_alert_for_user_assigned(
            organization_id=organization_id,
            questionnaire_id=input.questionnaire_id,
            created_by=info.context.user,
            user_assigned=user_assigned,
        )
        return UpdateQuestionAssignedUser(question=question.id)


class UpdateLibraryQuestionStatus(graphene.Mutation):
    class Arguments:
        input = UpdateLibraryQuestionStatusInput(required=True)

    updated = graphene.String()

    @laika_service(
        permission='library.change_question',
        exception_msg='Failed to update library question.',
        revision_name='Update library question',
    )
    def mutate(self, info, input):
        question_id = input.get('question_id')
        new_status = input.get('status')
        organization = info.context.user.organization

        QuestionService.validate_question_status(status=input.get('status'))

        update_library_question_status(question_id, organization, new_status)

        return UpdateLibraryQuestionStatus(updated=question_id)


class AddEquivalentQuestion(graphene.Mutation):
    class Arguments:
        input = EquivalentQuestionInput(required=True)

    updated = graphene.Boolean()

    @laika_service(
        permission='library.change_question',
        exception_msg='Failed to add equivalent Question',
    )
    def mutate(self, info, input: EquivalentQuestionInput):
        QuestionService.add_equivalent_question(
            organization_id=info.context.user.organization.id,
            question_id=input.question_id,
            equivalent_question_id=input.equivalent_question_id,
        )

        return AddEquivalentQuestion(updated=True)


class RemoveEquivalentQuestion(graphene.Mutation):
    class Arguments:
        input = EquivalentQuestionInput(required=True)

    updated = graphene.Boolean()

    @laika_service(
        permission='library.change_question',
        exception_msg='Failed to remove equivalent Question',
    )
    def mutate(self, info, input: EquivalentQuestionInput):
        QuestionService.remove_equivalent_question(
            organization_id=info.context.user.organization.id,
            question_id=input.question_id,
            equivalent_question_id=input.equivalent_question_id,
        )

        return RemoveEquivalentQuestion(updated=True)


class UpdateQuestionAnswer(graphene.Mutation):
    class Arguments:
        input = UpdateQuestionAnswerInput(required=True)

    updated = graphene.Boolean()

    @laika_service(
        permission='library.change_question', exception_msg='Failed to update question'
    )
    def mutate(self, info, input: UpdateQuestionAnswerInput):
        question = QuestionService.update_question_answer(
            organization_id=info.context.user.organization.id,
            question_id=input.question_id,
            answer_type=input.answer_type,
            answer_text=input.answer_text,
            user=info.context.user,
        )
        update_library_question_status(
            f'{input.question_id}', info.context.user.organization, STATUS_IN_PROGRESS
        )

        notify_library_entry_answer_modification(
            info, question.library_entry, [question]
        )

        question_search_index.add_to_index([question])

        return UpdateQuestionAnswer(updated=True)


class UseQuestionAnswer(graphene.Mutation):
    class Arguments:
        input = EquivalentQuestionInput(required=True)

    question = graphene.Field(QuestionType)
    equivalent_question = graphene.Field(QuestionType)

    @laika_service(
        permission='library.change_question', exception_msg='Failed to use answer'
    )
    def mutate(self, info, input: EquivalentQuestionInput):
        question, equivalent_question = QuestionService.use_answer(
            organization_id=info.context.user.organization.id,
            question_id=input.question_id,
            equivalent_id=input.equivalent_question_id,
        )

        notify_library_entry_answer_modification(
            info, equivalent_question.library_entry, [equivalent_question]
        )

        question_search_index.add_to_index([equivalent_question])

        return UseQuestionAnswer(
            question=question, equivalent_question=equivalent_question
        )


class UpdateLibraryQuestion(graphene.Mutation):
    class Arguments:
        input = UpdateLibraryQuestionInput(required=True)

    updated = graphene.Boolean()

    @laika_service(
        permission='library.change_libraryentry',
        exception_msg='Failed to update question. Please try again.',
        revision_name='Updated Question',
    )
    def mutate(self, info, input):
        user = info.context.user
        organization = user.organization
        question_id = input.get('question_id')

        question_to_update = get_question_by_id(
            organization_id=organization.id, question_id=question_id
        )

        if 'question_text' in input:
            QuestionService.update_question_text(
                organization=organization,
                question_id=question_id,
                question_text=input.get('question_text'),
            )

        if 'answer' in input:
            QuestionService.update_library_question_answer(
                question_to_update=question_to_update,
                user=user,
                answer_text=input['answer'].get('text', ''),
                short_answer_text=input['answer'].get('short_text', ''),
            )

        question_updated = get_question_by_id(
            organization_id=organization.id, question_id=question_id
        )

        question_search_index.add_to_index([question_updated])

        return UpdateLibraryQuestion(updated=True)


class DeleteLibraryQuestion(graphene.Mutation):
    class Arguments:
        input = DeleteLibraryQuestionInput(required=True)

    deleted = graphene.Boolean()

    @laika_service(
        permission='library.delete_question',
        exception_msg='Failed to delete Library Question',
    )
    def mutate(self, info, input: DeleteLibraryQuestionInput):
        organization = info.context.user.organization
        QuestionService.delete_question_from_library(
            question_id=input.question_id,
            organization_id=organization.id,
        )
        organization_has_suggestions = Question.objects.filter(
            equivalent_suggestions__isnull=False,
            library_entry__organization=organization,
        ).exists()

        if not organization_has_suggestions:
            QuestionService.remove_suggestions_alert(organization)

        return DeleteLibraryQuestion(deleted=True)


class ResolveEquivalentSuggestion(graphene.Mutation):
    class Arguments:
        input = ResolveEquivalentSuggestionInput(required=True)

    resolved = graphene.Boolean()

    @laika_service(
        permission='library.change_libraryentry',
        exception_msg='''
            Failed to resolve equivalent suggestion. Please try again.
        ''',
        revision_name='Resolve equivalent suggestion',
    )
    def mutate(self, info, input: ResolveEquivalentSuggestionInput):
        existing_question_id = input.existing_question_id
        equivalent_suggestion_id = input.equivalent_suggestion_id
        chosen_question_id = input.chosen_question_id
        answer_text = input.answer_text
        organization = info.context.user.organization
        user = info.context.user

        QuestionService.resolve_equivalent_suggestion(
            existing_question_id=existing_question_id,
            equivalent_suggestion_id=equivalent_suggestion_id,
            chosen_question_id=chosen_question_id,
            answer_text=answer_text,
            organization=organization,
            user=user,
        )

        QuestionService.remove_suggestions_alert(organization)

        return ResolveEquivalentSuggestion(resolved=True)


class AddDocumentsQuestionnaireDataroom(graphene.Mutation):
    class Arguments:
        input = AddDocumentsQuestionnaireDataroomInput(required=True)

    document_ids = graphene.List(graphene.String)

    @transaction.atomic
    @create_revision('Documents added to dataroom')
    @laika_service(
        permission='dataroom.add_dataroomevidence',
        exception_msg='Failed to add documents to questionnaire dataroom',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        questionnaire_name = input.questionnaire_name

        dataroom, created = Dataroom.objects.get_or_create(
            organization=organization, name=f'{questionnaire_name} Dataroom'
        )

        if created:
            questionnaire = Questionnaire.objects.get(
                name=questionnaire_name, organization=organization
            )
            questionnaire.dataroom = dataroom
            questionnaire.save()

        uploaded_files = input.get('uploaded_files', [])
        documents = input.get('documents', [])
        policies = input.get('policies', [])
        time_zone = input.time_zone

        document_ids = DataroomService.add_documents_to_dataroom(
            organization=organization,
            dataroom=dataroom,
            uploaded_files=uploaded_files,
            documents=documents,
            policies=policies,
            time_zone=time_zone,
        )

        return AddDocumentsQuestionnaireDataroom(document_ids=document_ids)
