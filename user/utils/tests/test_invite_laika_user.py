from unittest.mock import patch

import pytest

from user.utils.invite_laika_user import send_invite

user_dict = {
    'Email': 'john@doe.com',
    'First Name': ' John',
    'Last Name': ' Doe',
    'Role': 'admin',
}


@pytest.mark.functional()
def test_send_invite(graphql_organization):
    with patch(
        'user.utils.invite_laika_user.send_invite_email'
    ) as send_invite_user_email:
        email = 'john@doe.com'
        payload = {
            'email': email,
            'name': 'John',
            'message': 'Hi there',
            'password': '123',
            'role': 'OrganizationAdmin',
        }
        send_invite(payload)
        call_args = send_invite_user_email.call_args[0]
        actual_email, email_context = call_args
        assert email == actual_email
        assert payload.get('message') == email_context.get('message')
        assert payload.get('password') == email_context.get('password')
