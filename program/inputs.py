import graphene

from comment.inputs import CommentInput
from laika import types
from program.models import Program, SubTask, Task


class TaskInput(object):
    name = graphene.String()
    category = graphene.String()
    tier = graphene.String()
    description = graphene.String(default_value='')
    program_id = graphene.String()
    overview = graphene.String()
    implementation_notes = graphene.String()


class CreateTaskInput(TaskInput, types.DjangoInputObjectBaseType):
    name = graphene.String(required=True)
    category = graphene.String(required=True)
    tier = graphene.String(required=True)
    program_id = graphene.String(required=True)

    class InputMeta:
        model = Task


class UpdateTaskInput(TaskInput, types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)

    class InputMeta:
        model = Task


class UpdateTaskNotesInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    implementation_notes = graphene.String()

    class InputMeta:
        model = Task


class ProgramInput(object):
    name = graphene.String()
    description = graphene.String()
    program_lead_email = graphene.String()


class UpdateProgramInput(ProgramInput, types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)

    class InputMeta:
        model = Program


class SubTaskInput(object):
    text = graphene.String()
    assignee_email = graphene.String()
    status = graphene.String()
    group = graphene.String()
    badges = graphene.String()
    due_date = graphene.Date()
    priority = graphene.String()
    requires_evidence = graphene.Boolean()


class CreateSubTaskInput(SubTaskInput, types.DjangoInputObjectBaseType):
    text = graphene.String(required=True)
    group = graphene.String(required=True)
    priority = graphene.String(required=True)
    requires_evidence = graphene.Boolean(default=False)
    task_id = graphene.String(required=True)

    class InputMeta:
        model = SubTask


class UpdateSubTaskInput(SubTaskInput, types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)

    class InputMeta:
        model = SubTask


class UpdateSubTaskPartialInput(types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)
    status = graphene.String()
    assignee_email = graphene.String()
    completed_at = graphene.String()
    due_date = graphene.Date()

    class InputMeta:
        model = SubTask


class UpdateSubTaskStatusInput(types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)
    status = graphene.String(required=True)
    completed_at = graphene.String(required=True)

    class InputMeta:
        model = SubTask


class UpdateSubTaskDueDateInput(types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)
    due_date = graphene.Date()

    class InputMeta:
        model = SubTask


class UpdateSubTaskAssigneeInput(types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)
    assignee_email = graphene.String()

    class InputMeta:
        model = SubTask


class DeleteSubTaskInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)


class AddSubTaskEvidenceInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    uploaded_files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)
    other_evidence = graphene.List(graphene.String)
    teams = graphene.List(graphene.String)
    officers = graphene.List(graphene.String)
    time_zone = graphene.String(required=True)


class DeleteSubTaskEvidenceInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    evidence_id = graphene.String(required=True)


class AddTaskReplyInput(CommentInput, graphene.InputObjectType):
    task_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class UpdateTaskCommentInput(CommentInput, graphene.InputObjectType):
    task_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class DeleteTaskCommentInput(graphene.InputObjectType):
    task_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class UpdateCommentStateInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    task_id = graphene.String(required=True)
