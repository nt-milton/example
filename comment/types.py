import graphene

from comment.models import Comment
from user.types import UserType


class BaseCommentType(graphene.ObjectType):
    id = graphene.Int(required=True)
    owner = graphene.Field(UserType)
    owner_name = graphene.String(required=True)
    content = graphene.String(required=True)
    created_at = graphene.DateTime(required=True)
    updated_at = graphene.DateTime(required=True)
    is_deleted = graphene.Boolean(default_value=False)
    state = graphene.String()


class CommentType(BaseCommentType, graphene.ObjectType):
    replies = graphene.List(BaseCommentType)


# TODO: Use the new type for queries
class AppCommentType(BaseCommentType, graphene.ObjectType):
    class Meta:
        model = Comment

    replies = graphene.List(BaseCommentType)

    def resolve_replies(self, info):
        return self.replies.all().filter(is_deleted=False).order_by('created_at')
