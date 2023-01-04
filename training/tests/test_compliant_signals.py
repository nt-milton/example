from datetime import datetime

import pytest

from training.models import Alumni, Training
from training.signals import is_security_training_complete
from user.models import BACKGROUND_CHECK_STATUS_PASSED
from user.utils.compliant import is_user_compliant_completed


@pytest.fixture
def training(graphql_user):
    return Training.objects.create(
        organization=graphql_user.organization,
        name='Test Training',
        roles=['SuperAdmin'],
        category='Asset Management',
        description='Test Description',
    )


@pytest.mark.functional
def test_is_compliant(graphql_user):
    # Arrange
    graphql_user.security_training = True
    graphql_user.background_check_passed_on = datetime.now()
    graphql_user.background_check_status = BACKGROUND_CHECK_STATUS_PASSED

    # Act
    result = is_user_compliant_completed(graphql_user)

    # Assert
    assert result


@pytest.mark.functional
def test_security_training_completed(graphql_user, training):
    # Arrange
    Alumni.objects.create(user=graphql_user, training=training)

    # Act
    result = is_security_training_complete(graphql_user, [training.id])

    # Assert
    assert result


@pytest.mark.functional
def test_security_training_not_completed(graphql_user, training):
    # Act
    result = is_security_training_complete(graphql_user, [training.id])

    # Assert
    assert result is False
