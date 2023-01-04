import graphene
from graphene_django.types import DjangoObjectType

from access_review.utils import get_control_access_review
from alert.types_utils import ALERT_TYPE_RESOLVE_HELPERS, ALERT_TYPES_INDEX_HELPER
from alert.utils import (
    get_audit_from_alert,
    get_control_from_action_item,
    get_evidence_from_alert,
    get_policy_from_alert,
    get_requirement_from_alert,
    is_background_check_alert,
    is_control_action_item_period_alert,
    is_laika_object_alert,
    is_policy_comment_alert,
    is_requirement_comment_alert,
    is_user_alert,
)
from laika.types import PaginationResponseType
from seeder.models import Seed, SeedAlert
from vendor.models import VendorDiscoveryAlert

from .constants import ALERT_ACTIONS, ALERT_TYPES
from .models import Alert, PeopleDiscoveryAlert
from .tasks import get_task_and_content_by_alert_type
from .utils import (
    get_action_item_from_alert,
    get_control_from_alert,
    get_library_entry_suggestions_from_alert,
    get_questionnaire_from_alert,
    is_access_review_alert,
    is_audit_alert,
    is_control_action_item_assignment_alert,
    is_control_comment_alert,
    is_discovery_alert,
    is_draft_report_comment_alert,
    is_evidence_comment_alert,
    is_library_entry_suggestions_alert,
    is_playbook_alert,
    is_question_assignment_alert,
)

DISCOVERY_MODELS = {
    'VENDOR_DISCOVERY': VendorDiscoveryAlert,
    'PEOPLE_DISCOVERY': PeopleDiscoveryAlert,
}


def get_alert_url(alert):
    if is_evidence_comment_alert(alert.type):
        evidence = get_evidence_from_alert(alert)
        return f'audits/{evidence.audit.id}/evidence-detail/{evidence.id}'
    elif is_audit_alert(alert.type):
        audit_alert = alert.audit_alert.filter(alert=alert).first()
        audit = audit_alert.audit
        return f'audits/{audit.id}'
    elif is_control_comment_alert(alert.type):
        control = get_control_from_alert(alert)
        return f'controls/{control.id}'
    elif is_policy_comment_alert(alert.type):
        policy = get_policy_from_alert(alert)
        return f'policies/{policy.id}'
    elif is_playbook_alert(alert.type):
        alert_info_related = get_task_and_content_by_alert_type(alert=alert)
        task = alert_info_related.get('task')
        return f'{task.program.id}/{task.id}'
    elif is_laika_object_alert(alert.type):
        laika_object_alert = alert.laika_object_alert.first()
        if laika_object_alert is None:
            return 'not-found'
        lo_id = laika_object_alert.laika_object.data['Id']
        return f'lob/background_check?object={lo_id}'
    elif is_access_review_alert(alert.type):
        access_review_control = get_control_access_review(
            alert.receiver.organization.id
        )
        if access_review_control is None:
            return 'not-found'
        return f'controls/{access_review_control.id}'


class AlertType(graphene.ObjectType):
    class Meta:
        model = Alert

    id = graphene.String()
    sender_name = graphene.String()
    receiver_name = graphene.String()
    action = graphene.String()
    url = graphene.String()
    task_name = graphene.String()
    type = graphene.String()
    subtask_group = graphene.String()
    created_at = graphene.DateTime()
    comment_id = graphene.ID()
    comment_state = graphene.String()
    audit_type = graphene.String()
    quantity = graphene.Int()
    organization_name = graphene.String()
    evidence_name = graphene.String()
    audit_name = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    control_name = graphene.String()
    policy_name = graphene.String()
    action_item_description = graphene.String()
    comment_pool = graphene.String()
    access_review_name = graphene.String()

    def resolve_access_review_name(self, info):
        if is_access_review_alert(self.type):
            return self.access_review_alert.first().access_review.name

    def resolve_receiver_name(self, info):
        return self.receiver.first_name

    def resolve_action(self, info):
        return ALERT_ACTIONS.get(self.type) or None

    def resolve_url(self, info):
        index_helper = ALERT_TYPES_INDEX_HELPER.get(self.type)
        if index_helper is not None:
            methods = ALERT_TYPE_RESOLVE_HELPERS.get(index_helper, {})
            return methods.get('resolve_url', lambda x: '')(self)
        return get_alert_url(self)

    def resolve_task_name(self, info):
        if is_playbook_alert(self.type):
            alert_info_related = get_task_and_content_by_alert_type(alert=self)
            task = alert_info_related.get('task')
            return task.name

    def resolve_subtask_group(self, info):
        if is_playbook_alert(self.type):
            alert_info_related = get_task_and_content_by_alert_type(alert=self)
            return alert_info_related.get('subtask_group')

    def resolve_comment_id(self, info):
        if is_playbook_alert(self.type):
            alert_info_related = get_task_and_content_by_alert_type(alert=self)
            comment = alert_info_related.get('comment')
            comment_id = comment.id if comment else None
            return comment_id

    def resolve_comment_state(self, info):
        if is_playbook_alert(self.type):
            alert_info_related = get_task_and_content_by_alert_type(alert=self)
            comment = alert_info_related.get('comment')
            comment_state = comment.state if comment else None
            return comment_state

    def resolve_audit_type(self, info):
        if is_audit_alert(self.type):
            audit = get_audit_from_alert(self)
            return audit.audit_type
        elif is_draft_report_comment_alert(self.type):
            return (
                self.reply_alert.first()
                .reply.parent.draft_report_comments.first()
                .audit.audit_type
            )

    def resolve_quantity(self, info):
        if is_discovery_alert(self.type):
            discovery_alert = DISCOVERY_MODELS[self.type].objects.get(alert=self)
            return discovery_alert.quantity

        if is_library_entry_suggestions_alert(self.type):
            suggestions = get_library_entry_suggestions_from_alert(self)
            return suggestions.quantity

    def resolve_organization_name(self, info):
        if is_audit_alert(self.type):
            audit = get_audit_from_alert(self)
            return audit.organization.name

    def resolve_evidence_name(self, info):
        if is_evidence_comment_alert(self.type):
            evidence = get_evidence_from_alert(self)
            return evidence.name

    def resolve_comment_pool(self, info):
        return self.comment_pool

    def resolve_audit_name(self, info):
        if is_evidence_comment_alert(self.type):
            evidence = get_evidence_from_alert(self)
            return evidence.audit.name
        elif is_draft_report_comment_alert(self.type):
            return (
                self.reply_alert.first()
                .reply.parent.draft_report_comments.first()
                .audit.name
            )

    def resolve_first_name(self, info):
        return self.sender.first_name if self.sender else self.receiver.first_name

    def resolve_last_name(self, info):
        return self.sender.last_name if self.sender else self.receiver.last_name

    def resolve_control_name(self, info):
        if self.type == ALERT_TYPES['ACCESS_REVIEW_COMPLETE']:
            return get_control_access_review(
                self.access_review_alert.first().access_review.organization.id
            )
        if is_control_comment_alert(self.type):
            control = get_control_from_alert(self)
            return control.name

    def resolve_policy_name(self, info):
        if is_policy_comment_alert(self.type):
            policy = get_policy_from_alert(self)
            return policy.name

    def resolve_action_item_description(self, info):
        if is_control_action_item_assignment_alert(self.type):
            action_item = get_action_item_from_alert(self)
            return action_item.name

        if is_control_action_item_period_alert(self.type):
            action_item = get_action_item_from_alert(self)
            control = get_control_from_action_item(action_item)
            return control.name

        if is_question_assignment_alert(self.type):
            questionnaire = get_questionnaire_from_alert(self)
            return questionnaire.name

        if is_laika_object_alert(self.type):
            laika_object_alert = self.laika_object_alert.first()
            if laika_object_alert is None:
                return 'A record'
            data = laika_object_alert.laika_object.data
            first_name = data.get("First Name")
            last_name = data.get("Last Name")
            description = f'{first_name} {last_name}'
            if first_name is None and last_name is None:
                description = data.get('Email', '')
            return description

        if is_user_alert(self.type):
            user_alert = self.user_alert.first()
            if user_alert is None:
                return 'a user'
            return f'{user_alert.user.first_name} {user_alert.user.last_name}'

        if is_background_check_alert(self.type):
            return ''


class AlertsResponseType(graphene.ObjectType):
    data = graphene.List(AlertType)
    pagination = graphene.Field(PaginationResponseType)


class AuditorAlertType(graphene.ObjectType):
    class Meta:
        model = Alert

    id = graphene.String()
    sender_name = graphene.String()
    alert_type = graphene.String()
    audit_type = graphene.String()
    created_at = graphene.DateTime()
    audit_id = graphene.String()
    audit_name = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    evidence_id = graphene.String()
    evidence_name = graphene.String()
    requirement_name = graphene.String()
    requirement_id = graphene.String()
    comment_pool = graphene.String()
    organization_name = graphene.String()

    def resolve_first_name(self, info):
        return self.sender.first_name

    def resolve_last_name(self, info):
        return self.sender.last_name

    def resolve_alert_type(self, info):
        return self.type

    def resolve_sender_name(self, info):
        return self.sender.organization.name if self.sender.organization else None

    def resolve_audit_type(self, info):
        return get_audit_from_alert(self).audit_type

    def resolve_audit_id(self, info):
        return get_audit_from_alert(self).id

    def resolve_audit_name(self, info):
        return get_audit_from_alert(self).name

    def resolve_comment_pool(self, info):
        return self.comment_pool

    def resolve_evidence_id(self, info):
        return (
            get_evidence_from_alert(self).id
            if is_evidence_comment_alert(self.type)
            else None
        )

    def resolve_evidence_name(self, info):
        return (
            get_evidence_from_alert(self).name
            if is_evidence_comment_alert(self.type)
            else None
        )

    def resolve_requirement_id(self, info):
        requirement = get_requirement_from_alert(self)
        if not requirement:
            return None
        return requirement.id if is_requirement_comment_alert(self.type) else None

    def resolve_requirement_name(self, info):
        requirement = get_requirement_from_alert(self)
        if not requirement:
            return None
        return requirement.name if is_requirement_comment_alert(self.type) else None

    def resolve_organization_name(self, info):
        if is_audit_alert(self.type):
            audit = get_audit_from_alert(self)
            return audit.organization.name


class AuditorAlertsResponseType(graphene.ObjectType):
    new_alerts_number = graphene.Int()
    alerts = graphene.List(AuditorAlertType)
    pagination = graphene.Field(PaginationResponseType)


class SeedType(DjangoObjectType):
    class Meta:
        model = Seed


class ConciergeAlertType(graphene.ObjectType):
    class Meta:
        model = SeedAlert

    seed = graphene.Field(SeedType)

    def resolve_seed(self, info):
        return self.seed


class ConciergeAlertsResponseType(graphene.ObjectType):
    alerts = graphene.Field(ConciergeAlertType)
