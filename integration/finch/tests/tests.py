from integration.finch.implementation import work_email


def test_email_not_found_on_hr_user(caplog):
    def _get_log_details_message():
        return {
            'id': 'hr_123',
            'first_name': 'hr_firstname',
            'last_name': 'hr_lastname',
        }

    individual_without_emails = {
        'id': 'hr_123',
        'first_name': 'hr_firstname',
        'last_name': 'hr_lastname',
        'finch_uuid': '12345',
    }
    result = work_email(individual_without_emails)
    assert result == 'not_found'
    assert (
        f'Individual {_get_log_details_message()} does not have emails!.' in caplog.text
    )


def test_email_not_found_on_hr_user_without_id(caplog):
    def _get_log_details_message():
        return {'id': None, 'first_name': 'hr_firstname', 'last_name': 'hr_lastname'}

    individual_without_emails = {
        'first_name': 'hr_firstname',
        'last_name': 'hr_lastname',
        'finch_uuid': '12345',
    }
    result = work_email(individual_without_emails)
    assert result == 'not_found'
    assert (
        f'Individual {_get_log_details_message()} does not have emails!.' in caplog.text
    )


def test_email_not_found_on_hr_user_without_values(caplog):
    def _get_log_details_message():
        return {'id': None, 'first_name': None, 'last_name': None}

    individual_without_emails = {'finch_uuid': '12345'}
    result = work_email(individual_without_emails)
    assert result == 'not_found'
    assert (
        f'Individual {_get_log_details_message()} does not have emails!.' in caplog.text
    )
