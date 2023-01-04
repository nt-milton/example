from unittest.mock import MagicMock, patch

import pytest

from user.models import User

from .migrate_users import migrate_user

current_email = 'bryan@heylaika.com'
new_email = 'bryan+2@heylaika.com'


@pytest.mark.django_db
def test_migrate_partial_user(graphql_user):
    User.objects.create(email=current_email)
    migrate_user(current_email, new_email, MagicMock())
    assert User.objects.filter(email=new_email).exists()


@pytest.mark.django_db
@patch(
    'laika.aws.cognito.create_user',
    return_value={'username': 'new_username', 'temporary_password': 'pwd'},
)
@patch('laika.aws.cognito.delete_cognito_users')
@patch('user.utils.invite_laika_user.send_invite')
def test_migrate_full_user(
    send_invite_mock, delete_cognito_users_mock, create_user_mock, graphql_user
):
    User.objects.create(
        email=current_email,
        username='123456789',
        is_active=True,
        organization=graphql_user.organization,
    )
    migrate_user(current_email, new_email, MagicMock())
    assert User.objects.filter(email=new_email).exists()
    assert create_user_mock.called
    assert send_invite_mock.called
    assert ([current_email],) == delete_cognito_users_mock.call_args.args


@pytest.mark.django_db
@patch('laika.aws.cognito.create_user', side_effect=Exception('Something bad happened'))
@patch('laika.aws.cognito.delete_cognito_users')
@patch('user.utils.invite_laika_user.send_invite')
def test_migrate_full_user_failed(
    send_invite_mock, delete_cognito_users_mock, create_user_mock, graphql_user
):
    User.objects.create(
        email=current_email,
        username='123456789',
        is_active=True,
        organization=graphql_user.organization,
    )
    migrate_user(current_email, new_email, MagicMock())
    assert not User.objects.filter(email=new_email).exists()
