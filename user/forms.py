import csv
import logging
from typing import Tuple

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from urllib3.packages.six import StringIO

from laika.aws import cognito
from user import concierge_helpers
from user.constants import CONCIERGE
from user.models import User

logger = logging.getLogger(__name__)


def migrate_users(old_email, new_email) -> Tuple[bool, str]:
    logger.info(f'Migrating user from: {old_email} to: {new_email}')

    try:
        with transaction.atomic():
            current_user = User.objects.get(email=old_email)

            return update_existing_user(current_user, new_email)
    except Exception as e:
        logger.warning(f'Migration failed for person {old_email}')
        return False, f'User: {old_email}. {e}'


def update_existing_user(current_user, new_email) -> Tuple[bool, str]:
    if (
        current_user.is_active
        and current_user.username
        and current_user.role == CONCIERGE
    ):
        return update_cognito_user(current_user, new_email)
    else:
        return False, f'User {current_user.email} does not meet requirements'


def update_cognito_user(current_user, new_email) -> Tuple[bool, str]:
    old_email = current_user.email
    role = current_user.role
    # User role should be always Concierge
    if not role == CONCIERGE:
        return False, f'User {old_email} Role is not Concierge'

    user_data = {
        'role': role,
        'email': new_email,
        'first_name': current_user.first_name,
        'last_name': current_user.last_name,
    }

    try:
        cognito_user = cognito.create_user(user_data)
        current_user.username = cognito_user.get('username')
        current_user.email = new_email
        current_user.save()

        concierge_helpers.send_concierge_user_email_invitation(
            current_user, cognito_user
        )

        cognito.delete_cognito_users([old_email])
        return True, ''
    except Exception as e:
        return False, f'{e}'


class CSVField(forms.FileField):
    def __init__(self, *args, **kwargs):
        self.expected_fieldnames = kwargs.pop('expected_fieldnames', None)
        super(CSVField, self).__init__(*args, **kwargs)
        self.error_messages['required'] = 'You must select a file!'
        self.widget.attrs.update({'accept': '.csv,'})

    def clean(self, data, initial=None):
        value = super(CSVField, self).clean(data)
        reader = csv.DictReader(StringIO(data.read().decode('utf-8')), delimiter=',')
        # Check it's a valid CSV file
        try:
            fieldnames = reader.fieldnames
        except csv.Error:
            raise ValidationError('You must upload a valid CSV file')

        try:
            for row in reader:
                logger.info(f'row: {row}')
                old_email = row.get('old_email').lower()
                new_email = row.get('new_email').lower()

                if old_email == new_email:
                    logger.info(
                        'Skipping migration emails are the same: '
                        f'Old: {old_email} -'
                        f'New: {old_email}.'
                    )
                    continue
                success, message = migrate_users(old_email, new_email)
                if not success:
                    raise ValidationError(message)
                logger.info('Migration applied successfully')
        except Exception as e:
            logger.warning(f'Error: {e}')
            raise ValidationError(f'Migration is not complete. \nError: {e}')

        # Check the fieldnames are as specified, if requested
        if self.expected_fieldnames and fieldnames != self.expected_fieldnames:
            raise ValidationError(
                u'The CSV fields are expected to be "{0}"'.format(
                    u','.join(self.expected_fieldnames)
                )
            )

        return value


class MigratePolarisUsersForm(forms.Form):
    csv_file = CSVField(
        help_text='CSV formatted [old_email,new_email]',
        required=False,
        expected_fieldnames=['old_email', 'new_email'],
    )
