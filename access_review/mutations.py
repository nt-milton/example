from datetime import date, datetime
from typing import Any, Iterator

import graphene
from django.core.files import File
from django.db.models import Q

from access_review.constants import (
    ACCESS_REVIEW_COMPLETE_SUBJECT,
    ACCESS_REVIEW_REMINDER_SUBJECT,
    ACCESS_REVIEW_START_SUBJECT,
    AR_REVIEWERS_ACTION_ITEM_DESCRIPTION,
    AR_REVIEWERS_ACTION_ITEM_NAME,
    AR_REVIEWERS_ACTION_ITEM_TYPE,
)
from access_review.final_report import create_access_review_summary
from access_review.inputs import (
    AccessReviewInput,
    AccessReviewVendorPreferenceInput,
    AddAccessReviewEventInput,
    OverrideReviewerInput,
    SendAccessReviewReminderInput,
    UpdateAccessReviewInput,
    UpdateAccessReviewObjectInput,
    UpdateAccessReviewVendorInput,
)
from access_review.models import (
    AccessReview,
    AccessReviewAlert,
    AccessReviewObject,
    AccessReviewPreference,
    AccessReviewUserEvent,
    AccessReviewVendor,
    AccessReviewVendorPreference,
)
from access_review.types import (
    AccessReviewObjectType,
    AccessReviewPreferenceType,
    AccessReviewType,
    AccessReviewUserEventType,
    AccessReviewVendorPreferenceType,
    AccessReviewVendorType,
)
from access_review.utils import (
    get_access_review_control,
    get_in_progress_access_review,
    get_laika_object_permissions,
)
from action_item.evidence_handler import create_action_item_evidence
from action_item.models import ActionItem, ActionItemStatus
from action_item.utils import get_recurrent_last_action_item
from alert.constants import ALERT_TYPES
from control.evidence_handler import create_control_evidence
from control.models import Control
from control.tasks import FrequencyMapping
from evidence import constants
from integration.models import ConnectionAccount
from integration.tasks import run_vendor_integrations_per_organization
from laika.aws.ses import send_email
from laika.decorators import laika_service
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from objects.models import LaikaObject, LaikaObjectType
from organization.models import Organization
from program.utils.alerts import create_alert
from user.models import User
from user.types import UserType
from vendor.models import OrganizationVendor, Vendor

IMPLEMENTED_CONTROL = 'IMPLEMENTED'
RECURRENT_ACTION_ITEM = 'AC-R-009'
COMPLETED_ACTION_ITEM = 'completed'
CANCELED_ACCESS_REVIEW = 'canceled'


def update_access_review_from_action_item(action_item: ActionItem):
    metadata = action_item.metadata
    reference_id = metadata.get('referenceId')
    if reference_id != RECURRENT_ACTION_ITEM:
        return
    organization_id = metadata.get('organizationId')
    access_review_preference = AccessReviewPreference.objects.filter(
        organization__id=organization_id
    ).first()
    access_reviews_in_progress = AccessReview.objects.filter(
        organization__id=organization_id, status=AccessReview.Status.IN_PROGRESS
    )
    if (
        action_item.due_date
        and access_review_preference
        and not access_reviews_in_progress.exists()
    ):
        access_review_preference.due_date = action_item.due_date
        access_review_preference.save()


def create_access_review_vendors(
    access_review: AccessReview, organization: Organization
) -> Iterator[AccessReviewVendor]:
    in_scope_vendor_preferences = AccessReviewVendorPreference.objects.filter(
        organization=organization, in_scope=True
    )
    for in_scope_vendor in in_scope_vendor_preferences:
        access_review_vendor = AccessReviewVendor.objects.create(
            access_review=access_review,
            vendor=in_scope_vendor.vendor,
            synced_at=datetime.now(),
        )
        yield access_review_vendor


def extract_laika_objects(
    access_review_vendor: AccessReviewVendor,
) -> Iterator[LaikaObject]:
    connection_accounts = ConnectionAccount.objects.filter(
        integration__vendor=access_review_vendor.vendor,
        organization=access_review_vendor.access_review.organization,
    )
    object_types_ids = LaikaObjectType.objects.filter(
        type_name__in=['user', 'service_account']
    ).values('id')
    for connection_account in connection_accounts:
        for laika_object in LaikaObject.objects.filter(
            connection_account=connection_account,
            object_type_id__in=object_types_ids,
            deleted_at__isnull=True,
        ):
            yield laika_object


def create_access_review_object(
    access_review_vendor: AccessReviewVendor, laika_object: LaikaObject
):
    AccessReviewObject.objects.create(
        access_review_vendor=access_review_vendor,
        laika_object=laika_object,
        original_access=get_laika_object_permissions(laika_object),
    )


def create_access_review(
    organization: Organization, created_by: User, input: AccessReviewInput
) -> AccessReview:
    access_review = AccessReview.objects.create(
        organization=organization,
        name=input.name,
        due_date=input.due_date,
        notes=input.notes,
        created_by=created_by,
    )
    return access_review


def update_access_review_action_item(
    action_item: ActionItem, due_date: Any, frequency: str, user: User
):
    if not action_item.assignees.exists():
        action_item.assignees.set([user])
    action_item.due_date = due_date
    action_item.recurrent_schedule = frequency
    action_item.save()


def create_access_review_alerts(
    organization_id, receivers, alert_type, sender, sender_name, access_review
):
    for receiver in receivers:
        create_alert(
            organization_id,
            receiver,
            alert_type,
            alert_related_object={'access_review': access_review},
            alert_related_model=AccessReviewAlert,
            sender=sender,
            sender_name=sender_name,
        )


def get_reviewers(organization):
    return User.objects.filter(
        accessreviewvendorpreference__organization=organization,
        accessreviewvendorpreference__in_scope=True,
    )


def send_start_access_review_emails(
    organization: Organization,
    access_review: AccessReview,
    user: User,
    access_review_vendors: Iterator[AccessReviewVendor],
):
    subject = ACCESS_REVIEW_START_SUBJECT.format(access_review_name=access_review.name)
    reviewers = get_reviewers(organization)
    emails = [reviewer.email for reviewer in reviewers]
    laika_web = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
    access_review_url = f'{laika_web}/access-review/ongoing/'
    vendors_name_list = get_vendors_name_list(access_review_vendors)

    send_email(
        subject=subject,
        from_email=NO_REPLY_EMAIL,
        to=emails,
        template='access_review_start.html',
        template_context={
            'subject': subject,
            'due_date': access_review.due_date.strftime("%m/%d/%Y"),
            'vendors': vendors_name_list,
            'sender_name': user.first_name,
            'notes': access_review.notes,
            'access_review_url': access_review_url,
            'web_url': DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT'),
        },
    )


def send_complete_access_review_emails(
    access_review: AccessReview, reviewers: list[User], user: User
):
    subject = ACCESS_REVIEW_COMPLETE_SUBJECT.format(
        access_review_name=access_review.name
    )
    emails = [reviewer.email for reviewer in reviewers]
    laika_web = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
    access_review_url = f'{laika_web}/access-review?showReports'
    send_email(
        subject=subject,
        from_email=NO_REPLY_EMAIL,
        to=emails,
        template='access_review_complete.html',
        template_context={
            'subject': subject,
            'sender_name': user.first_name,
            'access_review_name': access_review.name,
            'access_review_url': access_review_url,
            'web_url': DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT'),
        },
    )


def create_access_review_objects_for_access_review_vendors(
    access_review_vendors: Iterator[AccessReviewVendor],
):
    for access_review_vendor in access_review_vendors:
        for laika_object in extract_laika_objects(access_review_vendor):
            create_access_review_object(access_review_vendor, laika_object)


def get_vendors_name_list(access_review_vendors: Iterator[AccessReviewVendor]):
    return [
        access_review_vendor.vendor.name
        for access_review_vendor in access_review_vendors
    ]


def create_access_review_action_item(
    organization_id: str,
    access_review_id: str,
    due_date: date,
) -> None:
    action_item = ActionItem.objects.create(
        name=AR_REVIEWERS_ACTION_ITEM_NAME,
        description=AR_REVIEWERS_ACTION_ITEM_DESCRIPTION,
        due_date=due_date,
        is_required=True,
        metadata={
            'type': AR_REVIEWERS_ACTION_ITEM_TYPE,
            'accessReviewId': access_review_id,
            'organizationId': organization_id,
        },
    )
    access_review_vendor_preferences = AccessReviewVendorPreference.objects.filter(
        organization=organization_id,
        in_scope=True,
    )
    access_review_vendor_reviewers = User.objects.filter(
        accessreviewvendorpreference__in=access_review_vendor_preferences
    )
    action_item.assignees.set(access_review_vendor_reviewers)


def get_dynamic_action_item(access_review_id: str) -> ActionItem:
    return ActionItem.objects.filter(
        metadata__type=AR_REVIEWERS_ACTION_ITEM_TYPE,
        metadata__accessReviewId=access_review_id,
    ).first()


class CreateAccessReview(graphene.Mutation):
    access_review = graphene.Field(AccessReviewType)

    class Arguments:
        input = AccessReviewInput(required=True)

    @laika_service(
        atomic=False,
        permission='access_review.add_accessreview',
        exception_msg='Failed to add Access Review',
    )
    def mutate(self, info, input):
        user = info.context.user
        organization = user.organization
        access_review = create_access_review(organization, user, input)
        AccessReviewUserEvent.objects.create(
            access_review=access_review,
            user=user,
            event=AccessReviewUserEvent.EventType.CREATE_ACCESS_REVIEW,
        )
        create_access_review_alerts(
            organization.id,
            get_reviewers(organization),
            ALERT_TYPES['ACCESS_REVIEW_START'],
            user,
            user.first_name,
            access_review,
        )

        access_review_vendors = list(
            create_access_review_vendors(access_review, organization)
        )
        create_access_review_objects_for_access_review_vendors(access_review_vendors)
        send_start_access_review_emails(
            organization, access_review, user, access_review_vendors
        )

        create_access_review_action_item(
            str(organization.id), str(access_review.id), access_review.due_date
        )

        access_review_preference = AccessReviewPreference.objects.filter(
            organization=organization
        ).first()

        action_item = get_recurrent_last_action_item(
            RECURRENT_ACTION_ITEM, organization.id
        )
        if action_item and access_review_preference:
            update_access_review_action_item(
                action_item,
                access_review_preference.due_date,
                access_review_preference.frequency,
                user,
            )

        return CreateAccessReview(access_review=access_review)


class OverrideReviewers(graphene.Mutation):
    class Arguments:
        input = OverrideReviewerInput(required=True)

    access_review_vendor_preference = graphene.Field(AccessReviewVendorPreferenceType)

    @laika_service(
        permission='access_review.change_accessreviewvendorpreference',
        exception_msg='Failed to override reviewer.',
    )
    def mutate(self, info, input):
        ar_vendor_preferences = AccessReviewVendorPreference.objects.get(
            vendor_id=input.vendor_preference_id,
            organization=info.context.user.organization,
        )
        users = User.objects.filter(username__in=input.reviewers_ids).values_list(
            'id', flat=True
        )
        ar_vendor_preferences.reviewers.set(users)
        return OverrideReviewers(access_review_vendor_preference=ar_vendor_preferences)


def create_access_review_vendor_preference(vendor_ids, organization):
    ar_vendor_preference_to_deactivate = AccessReviewVendorPreference.objects.filter(
        ~Q(vendor_id__in=vendor_ids),
        organization=organization,
    )
    ar_vendor_preference_to_deactivate.update(in_scope=False)
    for vendor_id in vendor_ids:
        organization_vendor = OrganizationVendor.objects.filter(
            vendor_id=vendor_id, organization=organization
        ).first()
        instance, _ = AccessReviewVendorPreference.objects.update_or_create(
            organization=organization,
            vendor_id=vendor_id,
            defaults={
                'in_scope': True,
                'vendor_id': vendor_id,
                'organization': organization,
            },
        )
        internal_stakeholders = (
            organization_vendor.internal_stakeholders.all()
            if organization_vendor
            else []
        )
        if not instance.reviewers.exists():
            instance.reviewers.set(internal_stakeholders)


class CreateAccessReviewPreference(graphene.Mutation):
    class Arguments:
        input = AccessReviewVendorPreferenceInput(required=True)

    access_review_preference = graphene.Field(AccessReviewPreferenceType)

    @laika_service(
        permission='access_review.change_accessreviewvendorpreference',
        exception_msg='Failed to update or create access review preferences.',
    )
    def mutate(self, info, input):
        user = info.context.user
        organization = user.organization
        access_review_preference, _ = AccessReviewPreference.objects.update_or_create(
            organization=organization,
            defaults={'frequency': input.frequency, 'due_date': input.due_date},
        )
        create_access_review_vendor_preference(input.vendor_ids, organization)
        action_item = get_recurrent_last_action_item(
            RECURRENT_ACTION_ITEM, organization.id
        )
        access_reviews_in_progress = get_in_progress_access_review(organization)
        if action_item and not access_reviews_in_progress:
            update_access_review_action_item(
                action_item,
                access_review_preference.due_date,
                access_review_preference.frequency,
                user,
            )
        return CreateAccessReviewPreference(
            access_review_preference=access_review_preference
        )


class UpdateAccessReview(graphene.Mutation):
    class Arguments:
        input = UpdateAccessReviewInput(required=True)

    access_review = graphene.Field(AccessReviewType)

    @laika_service(
        permission='access_review.change_accessreview',
        exception_msg='Failed to update access review.',
    )
    def mutate(self, info, input):
        access_review = AccessReview.objects.get(id=input.id)
        if input.status:
            access_review.status = input.status
        if input.status == CANCELED_ACCESS_REVIEW:
            action_item = get_dynamic_action_item(str(access_review.id))
            action_item.status = ActionItemStatus.NOT_APPLICABLE
            action_item.save()
        access_review.save()
        AccessReviewUserEvent.objects.create(
            access_review=access_review,
            user=info.context.user,
            event=AccessReviewUserEvent.EventType.CANCEL_ACCESS_REVIEW,
        )
        return UpdateAccessReview(access_review=access_review)


class UpdateAccessReviewObjects(graphene.Mutation):
    class Arguments:
        input = graphene.List(UpdateAccessReviewObjectInput, required=True)

    access_review_objects = graphene.List(AccessReviewObjectType)

    @laika_service(
        permission='access_review.change_accessreview',
        exception_msg='Failed to update access review.',
    )
    def mutate(self, info, input: list[UpdateAccessReviewObjectInput]):
        ids = [x.id for x in input]
        organization = info.context.user.organization
        review_objects = AccessReviewObject.objects.filter(
            id__in=ids, access_review_vendor__access_review__organization=organization
        )
        review_objects_map = {str(obj.id): obj for obj in review_objects}
        for change in input:
            review_object = review_objects_map[change.id]
            update(review_object, change)
        create_user_event_by_change(
            change, info.context.user, organization, review_objects
        )
        return UpdateAccessReviewObjects(
            access_review_objects=review_objects_map.values()
        )


def create_user_event_by_change(change, user: User, organization, review_objects):
    access_reviews_in_progress = get_in_progress_access_review(organization)
    event_types = get_event_types_by_change(change)
    for event_type in event_types:
        access_reviews_user_event = AccessReviewUserEvent.objects.create(
            access_review=access_reviews_in_progress, user=user, event=event_type
        )
        access_reviews_user_event.access_review_objects.add(*review_objects)


def get_event_types_by_change(change):
    event_types = []
    if change.confirmed is not None:
        event_types.append(
            AccessReviewUserEvent.EventType.REVIEWED_ACCOUNTS
            if change.confirmed
            else AccessReviewUserEvent.EventType.UNREVIEWED_ACCOUNTS
        )
    if change.notes is not None:
        event_types.append(
            AccessReviewUserEvent.EventType.CREATE_OR_UPDATE_ACCOUNTS_NOTES
        )
    if change.clear_attachment:
        event_types.append(AccessReviewUserEvent.EventType.CLEAR_ACCOUNT_ATTACHMENT)
    return event_types


def update(review_object: AccessReviewObject, change: UpdateAccessReviewObjectInput):
    if change.notes is not None:
        review_object.notes = change.notes
    if change.confirmed is not None:
        review_object.is_confirmed = change.confirmed
    if change.clear_attachment:
        review_object.note_attachment = None
    review_object.save()


class AddAccessReviewEvent(graphene.Mutation):
    class Arguments:
        input = AddAccessReviewEventInput(required=True)

    access_review_user_event = graphene.Field(AccessReviewUserEventType)

    @laika_service(
        permission='access_review.add_accessreviewuserevent',
        exception_msg='Failed to create access review user event.',
    )
    def mutate(self, info, input):
        access_review = AccessReview.objects.get(id=input.id)
        access_review_event, _ = AccessReviewUserEvent.objects.get_or_create(
            user=info.context.user, access_review=access_review, event=input.event_type
        )
        return AddAccessReviewEvent(access_review_user_event=access_review_event)


def get_new_preference_due_date(
    access_review_preference: AccessReviewPreference,
) -> date:
    frequency = access_review_preference.frequency.upper()
    frequency_value = FrequencyMapping[frequency].value
    old_due_date = access_review_preference.due_date
    return old_due_date + frequency_value.duration


class CompleteAccessReview(graphene.Mutation):
    class Arguments:
        access_review_id = graphene.ID(required=True)

    access_review = graphene.Field(AccessReviewType)

    @laika_service(
        permission='access_review.change_accessreview',
        exception_msg='Failed to complete access review.',
    )
    def mutate(self, info, access_review_id):
        access_review = AccessReview.objects.get(id=access_review_id)
        user = info.context.user
        final_report = create_access_review_summary(access_review, user)
        access_review.final_report = File(
            file=final_report, name=f'Summary Report - {access_review.name}.zip'
        )
        access_review.completed_at = datetime.now()
        access_review.status = AccessReview.Status.DONE
        access_review.save()
        AccessReviewUserEvent.objects.create(
            access_review=access_review,
            user=user,
            event=AccessReviewUserEvent.EventType.COMPLETE_ACCESS_REVIEW,
        )
        organization = user.organization
        action_item = get_dynamic_action_item(str(access_review.id))
        action_item.complete()
        create_access_review_evicence(organization, access_review)
        access_review_preference = AccessReviewPreference.objects.filter(
            organization=organization
        ).first()
        if access_review_preference:
            access_review_preference.due_date = get_new_preference_due_date(
                access_review_preference
            )
            access_review_preference.save()
        reviewers = get_reviewers(organization)
        create_access_review_alerts(
            organization.id,
            reviewers,
            ALERT_TYPES['ACCESS_REVIEW_COMPLETE'],
            user,
            user.first_name,
            access_review,
        )
        send_complete_access_review_emails(access_review, reviewers, user)
        return CompleteAccessReview(access_review=access_review)


def create_access_review_evicence(
    organization: Organization, access_review: AccessReview
):
    control = get_access_review_control(organization)
    if not control:
        return
    action_item = get_recurrent_last_action_item(RECURRENT_ACTION_ITEM, organization.id)
    create_report(action_item, organization, access_review, control)


def create_report(
    action_item: ActionItem,
    organization: Organization,
    access_review: AccessReview,
    control: Control,
):
    file = access_review.final_report.file
    if not file:
        return
    if action_item and action_item.status != COMPLETED_ACTION_ITEM:
        evidence = create_action_item_evidence(
            organization, action_item, file, constants.FILE
        )
    else:
        evidence = create_control_evidence(organization, control, file)

    evidence.name = file.name.split('/')[-1]
    evidence.save()


class RunVendorIntegrations(graphene.Mutation):
    class Arguments:
        vendor_id = graphene.ID(required=True)

    task_id = graphene.ID()

    @laika_service(
        permission='integration.change_connectionaccount',
        exception_msg='Failed to run vendor integrations',
    )
    def mutate(self, info, vendor_id):
        organization = info.context.user.organization
        async_task_result = run_vendor_integrations_per_organization.delay(
            organization.id, vendor_id
        )
        return RunVendorIntegrations(task_id=async_task_result.id)


class SendAccessReviewReminder(graphene.Mutation):
    class Arguments:
        input = SendAccessReviewReminderInput(required=True)

    reviewers = graphene.List(UserType)

    @laika_service(
        permission='access_review.change_accessreview',
        exception_msg='Failed to send access review reminder.',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        vendor = Vendor.objects.get(id=input.vendor_id)
        access_review_vendor_preference = AccessReviewVendorPreference.objects.get(
            vendor=vendor,
            organization=organization,
        )
        reviewers = access_review_vendor_preference.reviewers.all()
        subject = ACCESS_REVIEW_REMINDER_SUBJECT.format(vendor_name=vendor.name)
        emails = [reviewer.email for reviewer in reviewers]
        laika_web = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
        access_review_url = f'{laika_web}/access-review/ongoing/{vendor.id}'
        send_email(
            subject=subject,
            from_email=NO_REPLY_EMAIL,
            to=emails,
            template='reviewer_reminder_email.html',
            template_context={
                'subject': subject,
                'content': input.message.split('\n'),
                'access_review_url': access_review_url,
                'web_url': DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT'),
            },
        )
        return SendAccessReviewReminder(reviewers=reviewers)


class UpdateAccessReviewVendor(graphene.Mutation):
    class Arguments:
        input = UpdateAccessReviewVendorInput(required=True)

    access_review_vendor = graphene.Field(AccessReviewVendorType)

    @laika_service(
        permission='access_review.change_accessreviewvendor',
        exception_msg='Failed to update access review vendor.',
    )
    def mutate(self, info, input: UpdateAccessReviewVendorInput):
        access_review_vendor = AccessReviewVendor.objects.get(id=input.id)
        if input.status:
            access_review_vendor.status = input.status
            access_review_vendor.save()
            AccessReviewUserEvent.objects.create(
                access_review=access_review_vendor.access_review,
                user=info.context.user,
                event=AccessReviewUserEvent.EventType.COMPLETE_ACCESS_REVIEW_VENDOR,
                access_review_vendor=access_review_vendor,
            )
        return UpdateAccessReviewVendor(access_review_vendor=access_review_vendor)
