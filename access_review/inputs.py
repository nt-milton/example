import graphene


class AccessReviewInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    due_date = graphene.Date(required=True)
    notes = graphene.String()


class UpdateAccessReviewInput(AccessReviewInput, graphene.InputObjectType):
    id = graphene.String(required=True)
    name = graphene.String()
    due_date = graphene.Date()
    status = graphene.String()


class OverrideReviewerInput(graphene.InputObjectType):
    vendor_preference_id = graphene.String(required=True)
    reviewers_ids = graphene.List(graphene.String, required=True)


class AccessReviewVendorPreferenceInput(graphene.InputObjectType):
    due_date = graphene.DateTime(required=True)
    frequency = graphene.String(required=True)
    vendor_ids = graphene.List(graphene.String, required=True)


class UpdateAccessReviewObjectInput(graphene.InputObjectType):
    id = graphene.String(required=False)
    confirmed = graphene.Boolean(required=False)
    notes = graphene.String(required=False)
    clear_attachment = graphene.Boolean()


class AddAccessReviewEventInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    event_type = graphene.String(required=True)


class SendAccessReviewReminderInput(graphene.InputObjectType):
    vendor_id = graphene.ID(required=True)
    message = graphene.String(required=True)


class UpdateAccessReviewVendorInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    status = graphene.String(required=True)
