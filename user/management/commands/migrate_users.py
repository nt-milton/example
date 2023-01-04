import codecs
import csv

from django.core.management.base import BaseCommand
from django.db import transaction

from laika.aws import cognito
from laika.aws.s3 import s3_client
from user.constants import ROLE_ADMIN, ROLE_MEMBER
from user.models import User
from user.utils import invite_laika_user


class Command(BaseCommand):
    help = '''
        Migrate users from their current email to a new one.
        The command looks for a file within the laika-users-action bucket,
        you need to provide a file-name attribute with the name of the file
        stored in the bucket.
    '''

    def add_arguments(self, parser):
        parser.add_argument('--file-name', type=str)
        parser.add_argument('--bucket-name', type=str)

    def handle(self, *args, **options):
        bucket_name = options.get('bucket_name')
        file_name = options.get('file_name')
        rows = self.get_file_rows(bucket_name, file_name)
        for row in rows:
            old_email = row.get('old_email').lower()
            new_email = row.get('new_email').lower()
            if old_email == new_email:
                self.stdout.write(
                    f'Skipping migration old and new email are the same: {old_email}'
                )
                continue
            migrate_user(old_email, new_email, self.stdout)

    def get_file_rows(self, bucket_name, file_name):
        try:
            s3_response_object = s3_client.get_object(Bucket=bucket_name, Key=file_name)
            return csv.DictReader(codecs.getreader('utf-8')(s3_response_object['Body']))
        except Exception as e:
            self.stdout.write(f'There was a problem reading the file {file_name}')
            self.stdout.write(f'The error was: {e}')


def migrate_user(old_email, new_email, log):
    log.write('------------------------------------------------------')
    log.write(f'Migration Person from: {old_email} to: {new_email}')
    log.write()

    try:
        with transaction.atomic():
            current_user = User.objects.prefetch_related('organization').get(
                email=old_email
            )
            update_existing_user(current_user, new_email)
            log.write(f'Migration {new_email} was completed successfully')
    except Exception as e:
        log.write(f'Migration failed for person {old_email}')
        log.write(f'Something bad happened: {e}')
    log.write('------------------------------------------------------')


def update_existing_user(current_user, new_email):
    if current_user.is_active and current_user.username:
        update_cognito_user(current_user, new_email)
    else:
        update_partial_user(current_user, new_email)


def update_partial_user(current_user, new_email):
    current_user.email = new_email
    current_user.save()


def update_cognito_user(current_user, new_email):
    old_email = current_user.email
    organization = current_user.organization
    role = current_user.role
    # Cognito only have admin and member groups
    if role != ROLE_ADMIN:
        role = ROLE_MEMBER
    user_data = {
        'role': role,
        'email': new_email,
        'first_name': current_user.first_name,
        'last_name': current_user.last_name,
        'organization_id': organization.id,
        'tier': organization.tier,
        'organization_name': organization.name,
    }
    cognito_user = cognito.create_user(user_data)
    username = cognito_user.get('username')
    temporary_password = cognito_user.get('temporary_password')
    current_user.username = username
    current_user.email = new_email
    current_user.save()
    invite_laika_user.send_invite(
        {
            'email': new_email,
            'name': '',
            'message': '',
            'password': temporary_password,
            'role': current_user.role,
        }
    )
    cognito.delete_cognito_users([old_email])
