import logging
from datetime import datetime
from typing import List

from alert.constants import ALERT_TYPES
from integration.account import get_integration_laika_objects, integrate_account
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from objects.models import LaikaObject
from objects.system_types import BACKGROUND_CHECK
from objects.utils import (
    create_background_check_alerts,
    find_user_match_and_create_alerts_for_background_check,
)
from user.models import User

from ..encryption_utils import (
    decrypt_value,
    encrypt_value,
    get_decrypted_or_encrypted_value,
)
from ..log_utils import connection_data
from .checkr_types import Invitation, Report
from .constants import (
    CLEAR_CHECKR_STATUS,
    COMPLETE_CHECKR_STATUS,
    COMPLETED_CHECKR_INVITATION_STATUS,
    REPORT_COMPLETED_TYPE,
)
from .mapper import CHECKR_SYSTEM, map_background_checks
from .rest_client import fetch_auth_token, list_candidates, list_invitations
from .utils import (
    get_user_linked_in_laika_object,
    map_checkr_status,
    map_lo_to_background_check_type_attributes,
    update_laika_object_status,
)

N_RECORDS = get_integration_laika_objects(CHECKR_SYSTEM)

logger_name = __name__
logger = logging.getLogger(logger_name)


def callback(
    code, redirect_uri, connection_account: ConnectionAccount
) -> ConnectionAccount:
    if not code:
        raise ConfigurationError.denial_of_consent()
    data = connection_data(connection_account)

    response = fetch_auth_token(code, **data)
    response['access_token'] = encrypt_value(response.get('access_token'))
    connection_account.authentication = response
    connection_account.save()
    return connection_account


def raise_if_duplicate(connection_account: ConnectionAccount) -> None:
    access_token = connection_account.authentication.get('access_token')
    checkr_id = connection_account.authentication.get('checkr_account_id')
    current_organization = connection_account.organization
    checkr_connection_accounts: list[
        ConnectionAccount
    ] = ConnectionAccount.objects.filter(
        organization=current_organization,
        integration=connection_account.integration,
    ).exclude(
        id=connection_account.id
    )
    for checkr_connection_account in checkr_connection_accounts:
        decrypted_access_token = get_decrypted_or_encrypted_value(
            'access_token', checkr_connection_account
        )
        if (
            decrypted_access_token == decrypt_value(access_token)
            and checkr_connection_account.authentication['checkr_account_id']
            == checkr_id
        ):
            raise ConnectionAlreadyExists()


def run(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_attempt():
        get_decrypted_or_encrypted_value('access_token', connection_account)
        raise_if_duplicate(connection_account)
        access_token = connection_account.authentication.get('access_token')
        check_mapper = Mapper(
            map_function=map_background_checks,
            keys=['Id'],
            laika_object_spec=BACKGROUND_CHECK,
        )
        laika_objects_updated = get_laika_objects_updated(
            access_token, connection_account
        )
        update_laika_objects(connection_account, check_mapper, laika_objects_updated)

        integrate_account(connection_account, CHECKR_SYSTEM, N_RECORDS)


def check_candidate_status(laika_object, lo_data, last_report, users_to_update):
    user_linked = get_user_linked_in_laika_object(laika_object.data)

    if (
        last_report.get('status') in [COMPLETE_CHECKR_STATUS, CLEAR_CHECKR_STATUS]
        and not user_linked
    ):
        find_user_match_and_create_alerts_for_background_check(
            lo_data['user'].get('first_name'),
            lo_data['user'].get('last_name'),
            lo_data['user'].get('email'),
            laika_object.connection_account.organization.id,
        )
    if user_linked:
        if last_report.get('status') == COMPLETE_CHECKR_STATUS:
            user_linked.background_check_passed_on = datetime.today()
        user_linked.background_check_status = lo_data.get('people_status')
        users_to_update.append(user_linked)


def get_latest_report(reports: list[Report]) -> Report:
    reports.sort(key=lambda x: x['created_at'], reverse=True)
    return reports[0]


def get_laika_objects_updated(
    access_token: str, connection_account: ConnectionAccount
) -> List:
    laika_objects_updated = []
    users_to_update: List[User] = []
    candidates = list_candidates(access_token, **{'include': 'reports'})
    for candidate in candidates:
        candidate_id = candidate.get('id')
        try:
            laika_object = LaikaObject.objects.get(
                data__Id=candidate_id, connection_account=connection_account
            )
            lo_data = map_lo_to_background_check_type_attributes(laika_object.data)
        except LaikaObject.DoesNotExist:
            # If the candidate is not in the DB, it needs to be skipped
            logger.info(
                f'The Candidate Id {candidate_id} does not exist in '
                'the laika object table'
            )
            continue

        reports = candidate.get('reports', [])

        lo_data['user'] = {
            'first_name': candidate.get('first_name'),
            'last_name': candidate.get('last_name'),
            'email': candidate.get('email'),
        }

        if len(reports) == 0:
            laika_objects_updated.append(lo_data)
            continue

        should_create_change_status_alert = False
        # The webhook could not listen to invitation completed webhook
        if lo_data.get('initiation_date') is None:
            invitations: list[Invitation] = list_invitations(
                access_token,
                candidate_id=candidate_id,
                status=COMPLETED_CHECKR_INVITATION_STATUS,
            ).get('data', [])
            if len(invitations) > 0:
                lo_data['initiation_date'] = invitations[0].get('completed_at')
                lo_data['package'] = invitations[0].get('package')
                should_create_change_status_alert = True

        last_report = get_latest_report(reports)

        # Map the report status with the equivalences
        report_status_mapped = map_checkr_status(
            REPORT_COMPLETED_TYPE, last_report.get('status'), last_report.get('result')
        )

        # Review if the LO has a different status from checkr response and
        # updates the status
        if lo_data.get('status') != report_status_mapped.get('lo_status'):
            update_laika_object_status(lo_data, report_status_mapped)
            lo_data['estimated_completion_date'] = last_report.get(
                'estimated_completion_time'
            )
            should_create_change_status_alert = True

        if should_create_change_status_alert:
            create_background_check_alerts(
                alert_related_object={'laika_object': laika_object},
                alert_related_model='objects.LaikaObjectAlert',
                alert_type=ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS'),
                organization_id=laika_object.connection_account.organization.id,
            )

        check_candidate_status(laika_object, lo_data, last_report, users_to_update)

        laika_objects_updated.append(lo_data)

    User.objects.bulk_update(
        users_to_update, ['background_check_passed_on', 'background_check_status']
    )

    return laika_objects_updated
