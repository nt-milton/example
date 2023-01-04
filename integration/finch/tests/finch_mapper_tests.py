from integration.finch.implementation import phone_number, work_email


def test_work_email_is_selected():
    user = create_user(
        [('test@personal.com', 'personal'), ('test@heylaika.com', 'work')]
    )
    assert work_email(user) == 'test@heylaika.com'


def test_dont_use_personal_email():
    user = create_user(
        [('test@personal.com', 'personal'), ('test@personal2.com', 'personal')]
    )
    assert work_email(user) == 'not_found'


def test_dont_use_personal_phone_numbers():
    user_phones = create_phone([('5051234567', 'personal'), ('5051234123', 'personal')])
    assert phone_number(user_phones) is None


def create_user(emails):
    finch_emails = [{'data': email, 'type': type} for email, type in emails]
    return {'emails': finch_emails}


def create_phone(phones):
    finch_phones = [{'data': phone, 'type': phone_type} for phone, phone_type in phones]
    return {'phone_numbers': finch_phones}
