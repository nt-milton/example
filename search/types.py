import graphene


class SearchMetaType(graphene.ObjectType):
    id = graphene.String()
    program_id = graphene.String()


class SearchResponseType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    meta = graphene.Field(SearchMetaType)
    tags = graphene.List(graphene.String)
    search_type = graphene.String(name='type')
    logo = graphene.String()


class CustomFieldType(graphene.ObjectType):
    first_name = graphene.String()
    last_name = graphene.String()
    status = graphene.String()
    category = graphene.String()
    alias = graphene.String()
    website = graphene.String()


class CmdKBaseResultType(graphene.Interface):
    id = graphene.String()
    description = graphene.String()
    name = graphene.String()
    url = graphene.String()


class CmdKUserResultType(graphene.ObjectType):
    username = graphene.String()
    email = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKActionItemResultType(graphene.ObjectType):
    control = graphene.String()
    reference_id = graphene.String()
    due_date = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKControlResultType(graphene.ObjectType):
    reference_id = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKMonitorResultType(graphene.ObjectType):
    display_id = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKEvidenceRequestResultType(graphene.ObjectType):
    display_id = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKPolicyResultType(graphene.ObjectType):
    display_id = graphene.String()
    text = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKDriveResultType(graphene.ObjectType):
    text = graphene.String()
    owner = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKMentionResultType(graphene.ObjectType):
    mention = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKCommentResultType(graphene.ObjectType):
    owner = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKVendorResultType(graphene.ObjectType):
    text = graphene.String()

    class Meta:
        interfaces = (CmdKBaseResultType,)


class CmdKSearchResponseType(graphene.ObjectType):
    id = graphene.String()
    context = graphene.String()
    results = graphene.List(CmdKBaseResultType)


SearchTypes = [
    CmdKActionItemResultType,
    CmdKControlResultType,
    CmdKDriveResultType,
    CmdKPolicyResultType,
    CmdKVendorResultType,
    CmdKCommentResultType,
    CmdKMentionResultType,
    CmdKUserResultType,
    CmdKMonitorResultType,
    CmdKEvidenceRequestResultType,
]
