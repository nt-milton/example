import graphene

from laika import types


class QuestionInput(graphene.InputObjectType):
    aliases = graphene.List(graphene.String)
    default = graphene.String(required=True)


class AnswerInput(graphene.InputObjectType):
    text = graphene.String()
    short_text = graphene.String(default_value='')


class LibraryEntryInput(graphene.InputObjectType):
    category = graphene.String()
    question = graphene.Field(QuestionInput)
    answer = graphene.Field(AnswerInput)


class LibraryFileInput(graphene.InputObjectType):
    library_file = graphene.Field(types.InputFileType, required=True)


class BulkUpdateQuestionnaireStatusInput(graphene.InputObjectType):
    ids = graphene.List(graphene.String, required=True)
    status = graphene.String(required=True)


class DeleteQuestionnairesInput(graphene.InputObjectType):
    ids = graphene.List(graphene.String, required=True)
    delete_all_questions = graphene.Boolean(required=True)


class QuestionnaireQuestionInput(graphene.InputObjectType):
    text = graphene.String(required=True)
    metadata = graphene.JSONString(required=True)
    id = graphene.Int()
    library_entry_id = graphene.Int()


class CreateQuestionnaireQuestionInput(graphene.InputObjectType):
    questionnaire_id = graphene.Int(required=True)
    questions = graphene.List(QuestionnaireQuestionInput, required=True)
    overwrite_answer_addresses = graphene.Boolean(default=False)


class DeleteQuestionnaireQuestionInput(graphene.InputObjectType):
    text = graphene.String(required=True)
    formulas = graphene.List(graphene.String, required=True)


class DeleteQuestionnaireQuestionsInput(graphene.InputObjectType):
    questionnaire_id = graphene.Int(required=True)
    questions = graphene.List(DeleteQuestionnaireQuestionInput, required=True)


class UpdateQuestionAssignedUserInput(graphene.InputObjectType):
    question_id = graphene.String(required=True)
    questionnaire_id = graphene.String(required=True)
    user_assigned_email = graphene.String()


class UpdateLibraryQuestionStatusInput(graphene.InputObjectType):
    question_id = graphene.Int(required=True)
    status = graphene.String(required=True)


class EquivalentQuestionInput(graphene.InputObjectType):
    question_id = graphene.Int(required=True)
    equivalent_question_id = graphene.Int(required=True)


class UpdateQuestionAnswerInput(graphene.InputObjectType):
    question_id = graphene.Int(required=True)
    answer_type = graphene.String(required=True)
    answer_text = graphene.String(required=True)


class UpdateLibraryQuestionInput(graphene.InputObjectType):
    question_id = graphene.String(required=True)
    question_text = graphene.String()
    answer = graphene.Field(AnswerInput)


class DeleteLibraryQuestionInput(graphene.InputObjectType):
    question_id = graphene.Int(required=True)


class ResolveEquivalentSuggestionInput(graphene.InputObjectType):
    existing_question_id = graphene.Int(required=True)
    equivalent_suggestion_id = graphene.Int(required=True)
    chosen_question_id = graphene.Int()
    answer_text = graphene.String()


class AddDocumentsQuestionnaireDataroomInput(graphene.InputObjectType):
    questionnaire_name = graphene.String(required=True)
    uploaded_files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)
    time_zone = graphene.String(required=True)
