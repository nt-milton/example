from datetime import date, timedelta

import pytest

from alert.models import Alert, PeopleDiscoveryAlert
from integration.integration_utils.people_utils import integrate_people_discovery
from integration.tests import create_connection_account
from user.constants import ROLE_SUPER_ADMIN
from user.models import DISCOVERY_STATE_NEW, User
from user.tests import create_user


@pytest.mark.functional
def test_people_discovery_old_user_no_alert():
    connection_account = create_connection_account('vendor')
    create_user(
        connection_account.organization,
        email='test3@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='test',
        discovery_state=DISCOVERY_STATE_NEW,
    )
    yesterday = date.today() - timedelta(days=1)
    User.objects.all().update(date_joined=yesterday)

    integrate_people_discovery(connection_account)

    alerts_count = Alert.objects.count()
    people_discovery_alerts = PeopleDiscoveryAlert.objects.count()

    assert people_discovery_alerts == 0
    assert alerts_count == 0
