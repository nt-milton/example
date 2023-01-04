import graphene

from laika.decorators import audit_service, laika_service

from .constants import ALERT_TYPES
from .models import Alert


def update_new_alerts_viewed(user):
    new_alerts = Alert.objects.filter(receiver=user, viewed=False)
    if new_alerts:
        new_alerts.update(viewed=True)


def update_control_new_alerts_viewed(user):
    new_alerts = Alert.objects.filter(
        receiver=user,
        viewed=False,
        type__in=[ALERT_TYPES['CONTROL_MENTION'], ALERT_TYPES['CONTROL_REPLY']],
    )
    if new_alerts:
        new_alerts.update(viewed=True)


class UpdateAlertViewed(graphene.Mutation):
    success = graphene.Boolean(default_value=True)

    @laika_service(
        revision_name='Updated alert viewed field',
        permission='alert.change_alert',
        exception_msg='Cannot update alerts',
    )
    def mutate(self, info):
        user = info.context.user
        update_new_alerts_viewed(user)
        return UpdateAlertViewed()


class UpdateAuditorAlertViewed(graphene.Mutation):
    success = graphene.Boolean(default_value=True)

    @audit_service(
        permission='audit.change_auditalert', exception_msg='Cannot update alerts'
    )
    def mutate(self, info):
        user = info.context.user
        update_new_alerts_viewed(user)
        return UpdateAuditorAlertViewed()


class UpdateControlAlertViewed(graphene.Mutation):
    success = graphene.Boolean(default_value=True)

    @laika_service(
        permission='alert.change_alert',
        exception_msg='Cannot update control comments alerts',
    )
    def mutate(self, info):
        user = info.context.user
        update_control_new_alerts_viewed(user)
        return UpdateControlAlertViewed()
