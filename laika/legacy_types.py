import graphene


# These ones will be removed once tasks are migrated
class UserRep(graphene.ObjectType):
    _id = graphene.String(name='_id')
    email = graphene.String()
    firstName = graphene.String()
    id = graphene.String(required=True)
    lastName = graphene.String()


class TaskLegacyType(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    programId = graphene.String()
    programName = graphene.String(required=True)
    ownerDetails = graphene.Field(UserRep)
    status = graphene.String(required=True)
    dueDate = graphene.Float(required=True)
    category = graphene.String(required=True)
    priority = graphene.String(required=True)
    displayId = graphene.String(required=True)
