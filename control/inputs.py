import graphene

from action_item.models import ActionItem
from comment.inputs import CommentInput
from control.models import Control
from laika import types


class ControlInput(object):
    owner_emails = graphene.List(graphene.String)
    pillar_id = graphene.Int()
    name = graphene.String()
    tag_names = graphene.List(graphene.String)
    category = graphene.String()
    approver_email = graphene.String()
    frequency = graphene.String()
    description = graphene.String()
    administrator_email = graphene.String()
    implementation_notes = graphene.String()
    certification_section_ids = graphene.List(graphene.Int)


class CreateControlInput(ControlInput, types.DjangoInputObjectBaseType):
    name = graphene.String(required=True)
    description = graphene.String(required=True)
    category = graphene.String()
    frequency = graphene.String()

    class InputMeta:
        model = Control


class UpdateControlInput(ControlInput, types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)
    status = graphene.String()
    has_new_action_items = graphene.Boolean()
    implementation_notes = graphene.String()
    action_items_override_option = graphene.String()

    class InputMeta:
        model = Control


class NoteLaikaPaperInput(graphene.InputObjectType):
    laika_paper_title = graphene.String(required=True)
    laika_paper_content = graphene.String(default_value='', required=True)


class ControlEvidenceInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)
    other_evidence = graphene.List(graphene.String)
    teams = graphene.List(graphene.String)
    officers = graphene.List(graphene.String)
    time_zone = graphene.String(required=True)
    laika_paper = graphene.Field(lambda: NoteLaikaPaperInput, name='laika_paper')


class DeleteControlEvidenceInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    evidence = graphene.List(graphene.String)


class AddControlReplyInput(CommentInput, graphene.InputObjectType):
    control_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class DeleteControlCommentInput(graphene.InputObjectType):
    control_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class DeleteControlReplyInput(graphene.InputObjectType):
    comment_id = graphene.String(required=True)
    reply_id = graphene.String(required=True)


class UpdateControlCommentInput(CommentInput, graphene.InputObjectType):
    control_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)
    content = graphene.String()
    state = graphene.String()
    toggle_state = graphene.Boolean()


class UpdateControlReplyInput(CommentInput, graphene.InputObjectType):
    comment_id = graphene.String(required=True)
    reply_id = graphene.String(required=True)


class UpdateControlActionItemInput(types.DjangoInputObjectBaseType):
    class InputMeta:
        model = ActionItem

    action_item_id = graphene.String(required=True)
    due_date = graphene.DateTime()
    completion_date = graphene.DateTime()
    status = graphene.String()
    recurrent_schedule = graphene.String()
    owner = graphene.String()
    description = graphene.String()
    is_recurrent = graphene.Boolean()


class AddControlActionItemInput(types.DjangoInputObjectBaseType):
    class InputMeta:
        model = ActionItem

    name = graphene.String(required=True)
    description = graphene.String(required=True)
    is_required = graphene.Boolean(required=True)
    owner = graphene.String()
    due_date = graphene.DateTime(required=True)
    recurrent_schedule = graphene.String(required=True)
    control_id = graphene.String(required=True)
    metadata = graphene.JSONString()


class DeleteControlsInput(graphene.InputObjectType):
    ids = graphene.List(graphene.UUID, required=True)
    organization_id = graphene.UUID()


class UpdateControlFamilyOwnerInput(graphene.InputObjectType):
    control_family_id = graphene.String(required=True)
    owner_email = graphene.String(required=True)
    group_id = graphene.String()


class UpdateControlActionItemsInput(graphene.InputObjectType):
    control_id = graphene.UUID(required=True)
    overwrite_all = graphene.Boolean(default_value=False)
    owner = graphene.String()
    due_date = graphene.DateTime()
