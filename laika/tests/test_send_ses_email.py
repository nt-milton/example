from unittest.mock import patch

from laika.aws.ses import send_email, send_ses
from laika.settings import NO_REPLY_EMAIL


@patch('laika.aws.ses.ses.send_email', return_value={'MessageId': '1234'})
def test_send_ses_email(ses_mock):
    response = send_email(
        subject='Test',
        from_email='test@heylaika.com',
        to=['address@heylaika.com'],
        template='email/invite_user.html',
        template_context={},
    )
    ses_mock.assert_called_once()
    assert response == 1


@patch('laika.aws.ses.ses.send_email', return_value={'MessageId': '1234'})
def test_send_ses_email_exception(ses_mock):
    response = send_ses(
        NO_REPLY_EMAIL,
        ['test_test_test@ppppheylaika.com'],
        'Subject',
        '<div>HOLA</div>',
        'Message',
    )

    ses_mock.assert_called_once()
    assert response.get('MessageId') == '1234'
