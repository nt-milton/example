import logging

import graphene

from laika.auth import login_required, permission_required
from laika.decorators import audit_service, concierge_service, laika_service
from laika.types import PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import service_exception
from laika.utils.paginator import get_paginated_result
from seeder.models import SeedAlert
from vendor.models import VendorDiscoveryAlert

from .constants import ALERT_TYPES, DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from .models import Alert, PeopleDiscoveryAlert
from .mutations import (
    UpdateAlertViewed,
    UpdateAuditorAlertViewed,
    UpdateControlAlertViewed,
)
from .types import (
    AlertsResponseType,
    AuditorAlertsResponseType,
    ConciergeAlertsResponseType,
)

logger = logging.getLogger('alert_schema')

DISCOVERY_MODELS = {
    'VENDOR_DISCOVERY': VendorDiscoveryAlert,
    'PEOPLE_DISCOVERY': PeopleDiscoveryAlert,
}


class Query(object):
    alerts = graphene.Field(
        AlertsResponseType,
        pagination=graphene.Argument(PaginationInputType, required=False),
    )
    auditor_alerts = graphene.Field(
        AuditorAlertsResponseType,
        pagination=graphene.Argument(PaginationInputType, required=False),
    )
    concierge_alerts = graphene.Field(ConciergeAlertsResponseType)
    has_new_alerts = graphene.Boolean()
    number_new_alerts = graphene.Int()
    control_number_new_alerts = graphene.Int()

    @login_required
    @service_exception('Failed to get alerts')
    @permission_required('alert.view_alert')
    def resolve_alerts(self, info, **kwargs):
        user = info.context.user
        alerts = Alert.objects.filter(receiver=user).order_by('-created_at')
        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(alerts, page_size, page)
        return AlertsResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @audit_service(
        atomic=False,
        permission='audit.view_auditalert',
        exception_msg='Failed to get auditor alerts',
    )
    def resolve_auditor_alerts(self, info, **kwargs):
        user = info.context.user
        auditor_alerts = Alert.objects.filter(receiver=user).order_by('-created_at')
        new_alerts_number = auditor_alerts.filter(viewed=False).count()
        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(
            rows=auditor_alerts, page_size=page_size, page=page
        )
        return AuditorAlertsResponseType(
            new_alerts_number=new_alerts_number,
            alerts=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['auditor_alerts']),
        )

    @concierge_service(
        permission='user.view_concierge', exception_msg='Failed to get concierge alerts'
    )
    def resolve_concierge_alerts(self, info):
        user = info.context.user
        concierge_alerts = Alert.objects.filter(receiver=user).order_by('-created_at')

        recent_alert = concierge_alerts.first()

        if recent_alert and recent_alert.viewed is False:
            recent_alert.viewed = True
            recent_alert.save()

            seed_alert = SeedAlert.objects.get(alert=concierge_alerts.first())

            return ConciergeAlertsResponseType(alerts=seed_alert)

        return ConciergeAlertsResponseType(alerts=None)

    @login_required
    @service_exception('Failed to get alerts')
    @permission_required('alert.view_alert')
    def resolve_has_new_alerts(self, info, **kwargs):
        user = info.context.user
        alerts = Alert.objects.filter(receiver=user, viewed=False)
        return True if alerts else False

    @login_required
    @service_exception('Failed to get alerts')
    @permission_required('alert.view_alert')
    def resolve_number_new_alerts(self, info, **kwargs):
        user = info.context.user
        number_new_alerts = Alert.objects.filter(receiver=user, viewed=False).count()
        return number_new_alerts

    @laika_service(
        permission='alert.view_alert', exception_msg='Failed to get Control alerts'
    )
    def resolve_control_number_new_alerts(self, info, **kwargs):
        user = info.context.user
        number_new_alerts = Alert.objects.filter(
            receiver=user,
            viewed=False,
            type__in=[ALERT_TYPES['CONTROL_MENTION'], ALERT_TYPES['CONTROL_REPLY']],
        ).count()
        return number_new_alerts


class Mutation(object):
    update_alert_viewed = UpdateAlertViewed.Field()
    update_auditor_alert_viewed = UpdateAuditorAlertViewed.Field()
    update_control_alert_viewed = UpdateControlAlertViewed.Field()
