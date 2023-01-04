import pytest

from alert.constants import ALERT_TYPES
from alert.models import Alert
from objects.tests.factory import create_lo_with_connection_account
from user.constants import ROLE_ADMIN
from user.models import BACKGROUND_CHECK_STATUS_PASSED, User
from user.tests import create_user

from ...encryption_utils import encrypt_value
from ...exceptions import ConnectionAlreadyExists
from ...tests import create_connection_account
from .. import implementation
from ..implementation import get_laika_objects_updated
from ..mapper import CHECKR_SYSTEM
from .fake_api.fake_api import fake_checkr_api

EMAIL = 'jhon@heylaika.com'
EMAIL_TEST = 'leomessidev@heylaika.com'
INITIATION_DATE_NONE = {'Initiation Date': None}


def checkr_connection_account(**kwargs):
    return create_connection_account(
        'Checkr',
        authentication=dict(
            access_token=encrypt_value('MyToken'),
            checkr_account_id='accountId',
        ),
        configuration_state={},
        **kwargs
    )


@pytest.fixture
def connection_account():
    with fake_checkr_api():
        yield checkr_connection_account()


@pytest.fixture
def admin_user(graphql_organization):
    return create_user(
        graphql_organization, email=EMAIL, role=ROLE_ADMIN, first_name='john'
    )


def create_objects(organization, candidate_id, data=None):
    base_data = {
        'Id': candidate_id,
        'First Name': 'Leo',
        'Last Name': 'Messi',
        'email': 'leomessi@heylaika.com',
        'Link to People Table': None,
        'Initiation Date': '2022-06-24T14:50:51Z',
        'Package': 'tasker_standard',
        'Status': 'Pending',
    }
    if data is not None:
        base_data.update(data)
    laika_object, connection_account = create_lo_with_connection_account(
        organization, vendor_name=CHECKR_SYSTEM, data=base_data
    )

    return laika_object, connection_account


FAKE_ACCESS_TOKEN = encrypt_value('random')


@pytest.mark.functional
def test_update_laika_objects_with_checkr_data_invitation_complete(
    graphql_organization, admin_user
):
    candidate_id = '8744e26f908c2ccdceaa7de6'
    laika_object, connection_account = create_objects(
        graphql_organization, candidate_id, INITIATION_DATE_NONE
    )

    with fake_checkr_api():
        laika_object_updated = get_laika_objects_updated(
            FAKE_ACCESS_TOKEN, connection_account
        )
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
        alert = Alert.objects.filter(type=alert_type)
        user = laika_object_updated[0].get('user')
        assert alert.count() == 1
        assert user.get('first_name') == 'Leo'
        assert user.get('last_name') == 'Messi'
        assert user.get('email') == EMAIL_TEST
        assert laika_object_updated[0].get('package') == 'laika_driver_pro'


@pytest.mark.functional
def test_update_laika_objects_with_checkr_data_change_status(
    graphql_organization, admin_user
):
    candidate_id = '8744e26f908c2ccdceaa7de6'
    laika_object, connection_account = create_objects(
        graphql_organization, candidate_id, INITIATION_DATE_NONE
    )

    with fake_checkr_api():
        laika_object_updated = get_laika_objects_updated(
            FAKE_ACCESS_TOKEN, connection_account
        )
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
        alert = Alert.objects.filter(type=alert_type)
        user = laika_object_updated[0].get('user')
        assert alert.count() == 1
        assert user.get('first_name') == 'Leo'
        assert user.get('last_name') == 'Messi'
        assert user.get('email') == EMAIL_TEST
        assert laika_object_updated[0].get('status') == 'Clear'
        assert (
            laika_object_updated[0].get('estimated_completion_date')
            == '2022-06-27T00:00:00Z'
        )


@pytest.mark.functional
def test_update_laika_objects_with_checkr_data_report_complete(
    graphql_organization, admin_user
):
    candidate_id = '8744e26f908c2ccdceaa7de7'
    laika_object, connection_account = create_objects(
        graphql_organization, candidate_id, {'email': EMAIL}
    )

    with fake_checkr_api():
        laika_object_updated = get_laika_objects_updated(
            FAKE_ACCESS_TOKEN, connection_account
        )
        alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO')
        alert = Alert.objects.filter(type=alert_type)
        user = laika_object_updated[0].get('user')
        assert alert.count() == 1
        assert user.get('first_name') == 'Leo'
        assert user.get('last_name') == 'Messi'
        assert user.get('email') == EMAIL


@pytest.mark.functional
def test_update_laika_objects_with_checkr_data_report_complete_and_user_linked(
    graphql_organization, admin_user
):
    candidate_id = '8744e26f908c2ccdceaa7de8'
    laika_object, connection_account = create_objects(
        graphql_organization,
        candidate_id,
        {
            'email': EMAIL,
            "Link to People Table": {
                "id": admin_user.id,
                "email": admin_user.email,
                "lastName": admin_user.last_name,
                "username": admin_user.username,
                "firstName": admin_user.first_name,
            },
        },
    )

    with fake_checkr_api():
        laika_object_updated = get_laika_objects_updated(
            FAKE_ACCESS_TOKEN, connection_account
        )
        alert_status_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
        alert = Alert.objects.filter(type__in=[alert_status_type])
        user = laika_object_updated[0].get('user')
        user_linked = User.objects.get(id=admin_user.id)
        assert alert.count() == 1
        assert user.get('first_name') == 'Leo'
        assert user.get('last_name') == 'Messi'
        assert user.get('email') == EMAIL
        assert user_linked.background_check_passed_on is not None
        assert user_linked.background_check_status == BACKGROUND_CHECK_STATUS_PASSED


@pytest.mark.functional
def test_update_laika_objects_with_checkr_data_no_reports(graphql_organization):
    candidate_id = '8744e26f908c2ccdceaa7de6'
    laika_object, connection_account = create_objects(
        graphql_organization, candidate_id
    )

    with fake_checkr_api():
        laika_object_updated = get_laika_objects_updated(
            FAKE_ACCESS_TOKEN, connection_account
        )
        user = laika_object_updated[0].get('user')
        assert user.get('first_name') == 'Leo'
        assert user.get('last_name') == 'Messi'
        assert user.get('email') == EMAIL_TEST


@pytest.mark.functional
def test_update_laika_objects_with_checkr_data_candidate_not_exist(
    graphql_organization,
):
    laika_object, connection_account = create_objects(
        graphql_organization, '8744e26f908c2ccdceaa7d10'
    )

    with fake_checkr_api():
        laika_object_updated = get_laika_objects_updated(
            FAKE_ACCESS_TOKEN, connection_account
        )
        assert len(laika_object_updated) == 0


@pytest.mark.functional
def test_raise_if_is_duplicated(connection_account):
    created_by = create_user(
        connection_account.organization, email='heylaika+test+@heylaika.com'
    )
    create_connection_account(
        'Checkr-2',
        authentication={'access_token': 'MyToken', 'checkr_account_id': 'accountId'},
        organization=connection_account.organization,
        integration=connection_account.integration,
        created_by=created_by,
        configuration_state={},
    )
    with pytest.raises(ConnectionAlreadyExists):
        implementation.run(connection_account)
