import graphene

from fieldwork.types import evidence_comment_pools_enum


class DeleteCommentInput(graphene.InputObjectType):
    object_type = graphene.String(required=True)
    object_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class CommentInput(object):
    content = graphene.String(required=True)
    tagged_users = graphene.List(graphene.String)


class DeleteReplyInput(graphene.InputObjectType):
    comment_id = graphene.String(required=True)
    reply_id = graphene.String(required=True)


class UpdateReplyInput(CommentInput, graphene.InputObjectType):
    reply_id = graphene.String(required=True)


class AddReplyInput(CommentInput, graphene.InputObjectType):
    object_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)
    object_type = graphene.String(required=True)


class AddCommentOrReplyInput(CommentInput, graphene.InputObjectType):
    object_id = graphene.String(required=True)
    action_id = graphene.String(required=True)
    object_type = graphene.String(required=True)


class AddCommentInput(CommentInput, graphene.InputObjectType):
    object_id = graphene.String(required=True)
    object_type = graphene.String(required=True)
    pool = evidence_comment_pools_enum()
    page = graphene.String()


class UpdateCommentInput(CommentInput, graphene.InputObjectType):
    object_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)
    object_type = graphene.String(required=True)
    content = graphene.String()
    page = graphene.String()


class UpdateCommentStateInput(UpdateCommentInput):
    state = graphene.String()
