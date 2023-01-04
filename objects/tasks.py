import logging
from typing import List

from django.db.models import Q

from alert.constants import ALERT_TYPES, ALERT_TYPES_LAIKA_OBJECTS
from integration.checkr.mapper import CHECKR_SYSTEM
from integration.utils import get_oldest_connection_account_by_vendor_name
from laika.celery import app as celery_app
from objects.models import LaikaObject
from objects.utils import create_background_check_alerts
from organization.models import Organization

logger = logging.getLogger(__name__)


@celery_app.task(name='Find match for background check')
def find_match_for_lo_background_check(users: List, organization_id: str) -> None:
    try:
        organization = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        logger.error(f'The organization {organization_id} does not exits')
        return
    connection_account = get_oldest_connection_account_by_vendor_name(
        organization, CHECKR_SYSTEM
    )
    if connection_account is None:
        logger.error(
            f'The organization {organization.id} does not have a '
            'check connection account'
        )
        return
    for user in users:
        first_name = user.get('first_name')
        last_name = user.get('last_name')
        email = user.get('email')
        if first_name and last_name or email:
            lo_matches = LaikaObject.objects.filter(
                connection_account=connection_account,
                **{"data__Link to People Table__exact": None},
            ).filter(
                Q(
                    **{
                        "data__First Name__iexact": first_name,
                        "data__Last Name__iexact": last_name,
                    }
                )
                | Q(**{"data__Email__exact": email})
            )
            num_matches = len(lo_matches)
            alert_type = ALERT_TYPES_LAIKA_OBJECTS.get(
                'LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER', ''
            )
            if num_matches > 1:
                alert_type = ALERT_TYPES_LAIKA_OBJECTS.get(
                    'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER', ''
                )
            if num_matches > 0:
                create_background_check_alerts(
                    alert_related_object={'laika_object': lo_matches[0]},
                    alert_related_model='objects.LaikaObjectAlert',
                    alert_type=ALERT_TYPES.get(alert_type, ''),
                    organization_id=organization.id,
                )
                logger.info(
                    f'The user {first_name} {last_name} has '
                    f'{num_matches} match in LO Background Check'
                )
