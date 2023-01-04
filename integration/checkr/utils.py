import logging
from datetime import datetime

from alert.constants import ALERT_TYPES
from integration.checkr.constants import (
    CANCELED_CHECKR_STATUS,
    CANDIDATE_UPDATED_TYPE,
    CHECKR_STATUS_MAP,
    INVITATION_COMPLETED_TYPE,
    INVITATION_TYPE,
    PENDING_CHECKR_STATUS,
    REPORT_COMPLETED_TYPE,
    REPORT_CREATED_TYPE,
    REPORT_TYPE,
)
from integration.encryption_utils import decrypt_value
from integration.models import ConnectionAccount, Integration
from integration.store import update_laika_objects
from objects.models import LaikaObject
from objects.system_types import BackgroundCheck, LOAttribute
from objects.utils import (
    create_background_check_alerts,
    find_user_match_and_create_alerts_for_background_check,
)
from user.models import User
from vendor.models import Vendor

logger_name = __name__
logger = logging.getLogger(logger_name)


def get_connection_by_authentication_field(key, value):
    if key == 'checkr_account_id':
        return (
            ConnectionAccount.objects.filter(authentication__checkr_account_id=value)
            .order_by('id')
            .first()
        )
    vendor = Vendor.objects.get(name='Checkr')
    integration = Integration.objects.get(vendor=vendor)
    checkr_connection_accounts = ConnectionAccount.objects.filter(
        integration=integration
    ).order_by('id')
    for checkr_connection_account in checkr_connection_accounts:
        if decrypt_value(checkr_connection_account.authentication.get(key)) == value:
            return checkr_connection_account


def map_lo_to_background_check_type_attributes(data):
    new_object = {}
    bg_check = BackgroundCheck()
    attributes = [p for p in dir(bg_check) if not p.startswith('_')]
    for item in attributes:
        attr = getattr(bg_check, item, None)
        if isinstance(attr, LOAttribute):
            if item in ['first_name', 'last_name', 'email']:
                new_object.setdefault('user', {})
                new_object['user'][item] = data.get(attr.display_name)
            else:
                new_object[item] = data.get(attr.display_name)

    return new_object


def update_lo_data(
    event_type: str, object_type: str, new_data: dict, laika_object: LaikaObject
):
    lo_data = map_lo_to_background_check_type_attributes(laika_object.data)
    update_lo = False
    if event_type == INVITATION_COMPLETED_TYPE:
        lo_data['initiation_date'] = new_data.get('completed_at')
        lo_data['package'] = new_data.get('package')
        update_lo = True

    if event_type == CANDIDATE_UPDATED_TYPE:
        lo_data['user'] = {
            'first_name': new_data.get('first_name'),
            'last_name': new_data.get('last_name'),
            'email': new_data.get('email'),
        }
        update_lo = True

    if event_type == REPORT_CREATED_TYPE:
        lo_data['package'] = new_data.get('package')
        lo_data['estimated_completion_date'] = new_data.get('estimated_completion_time')
        update_lo = True

    if object_type == REPORT_TYPE or object_type == INVITATION_TYPE:
        candidate_status = (
            new_data.get('status')
            or laika_object.data.get('Status')
            or PENDING_CHECKR_STATUS
        )

        report_result = new_data.get('result', CANCELED_CHECKR_STATUS)
        candidate_parsed_status = map_checkr_status(
            event_type, candidate_status, report_result
        )
        update_laika_object_status(lo_data, candidate_parsed_status)
        update_lo = True

    return lo_data, update_lo


def map_checkr_status(event_type, status, result):
    status = CHECKR_STATUS_MAP.get(event_type, {}).get(status, {})
    if event_type == REPORT_COMPLETED_TYPE:
        return status.get(result, {})
    return status


def update_laika_object_status(laika_object, mapped_status):
    laika_object['status'] = mapped_status.get('lo_status')
    laika_object['people_status'] = mapped_status.get('people_status')


def get_user_linked_in_laika_object(data):
    user_linked = None
    user_linked_data = data.get("Link to People Table")
    if user_linked_data:
        user_id = user_linked_data.get('id')
        try:
            user_linked = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.exception(f'The user id linked {user_id} does not exist')

    return user_linked


def handle_checkr_events(
    event_type,
    object_type,
    candidate_object,
    laika_object,
    connection_account,
    check_mapper,
    user_linked=None,
):
    update_user_linked = False
    lo_data_updated, update_lo = update_lo_data(
        event_type, object_type, candidate_object, laika_object
    )
    report_in_progress_type = REPORT_TYPE and event_type != REPORT_COMPLETED_TYPE

    if update_lo:
        update_laika_objects(
            connection_account=connection_account,
            mapper=check_mapper,
            raw_objects=[lo_data_updated],
            cleanup_objects=False,
        )
    if (
        object_type == REPORT_TYPE or event_type == INVITATION_COMPLETED_TYPE
    ) and event_type is not REPORT_CREATED_TYPE:
        create_background_check_alerts(
            alert_related_object={'laika_object': laika_object},
            alert_related_model='objects.LaikaObjectAlert',
            alert_type=ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS'),
            organization_id=connection_account.organization.id,
        )
    if event_type == REPORT_COMPLETED_TYPE:
        find_user_match_and_create_alerts_for_background_check(
            laika_object.data.get('First Name'),
            laika_object.data.get('Last Name'),
            laika_object.data.get('Email'),
            connection_account.organization.id,
        )
        if user_linked:
            user_linked.background_check_passed_on = datetime.today()
            user_linked.background_check_status = lo_data_updated.get('people_status')
            update_user_linked = True

    if report_in_progress_type and user_linked:
        user_linked.background_check_status = lo_data_updated.get('people_status')
        user_linked.background_check_passed_on = None
        update_user_linked = True
    if update_user_linked:
        user_linked.save()
        logger.info(f'The user linked {user_linked.username} has been updated')
