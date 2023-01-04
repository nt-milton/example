import csv
import logging
import os
import re
import secrets
import string

import boto3
from django.db import migrations
from django.db.models import Q

from laika.okta.api import OktaApi
from laika.settings import ENVIRONMENT, LAIKA_BACKEND
from laika.utils.regex import URL_DOMAIN_NAME
from user.constants import OKTA_GROUPS_NAMES
from user.models import ROLES

CSV_FIELD_NAMES = ['first_name', 'last_name', 'organization', 'email', 'password']
LOCAL_ENVIRONMENT = 'local'
PROD_ENVIRONMENT = 'prod'
output_file = 'admin_users.csv'
logger = logging.getLogger('user')
OktaApi = OktaApi()
s3 = boto3.client('s3')


def upload_file_to_s3(file_name: str):
    with open(file_name, 'rb') as f:
        s3.upload_fileobj(f, f'{ENVIRONMENT}-ml-report', file_name)
    os.remove(file_name)


def create_user_entry(user, organization, email, password):
    return {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'organization': organization.name,
        'email': email,
        'password': password,
    }


def generate_random_password() -> str:
    password_length = 20
    random_source = string.ascii_letters + string.digits + string.punctuation
    password_requirements = (
        secrets.choice(string.ascii_lowercase)  # type: ignore
        + secrets.choice(string.ascii_uppercase)  # type: ignore
        + secrets.choice(string.digits)  # type: ignore
        + secrets.choice(string.punctuation)  # type: ignore
    )

    random_pass = [
        secrets.choice(random_source) for _ in range(password_length)  # type: ignore
    ]
    return password_requirements + ''.join(random_pass)


def generate_email_address(website: str, email: str) -> str:
    tokens = email.split('@')
    matches = re.search(URL_DOMAIN_NAME, website)
    new_email = f'{tokens[0]}+{matches.group(1)}@{tokens[1]}'  # type: ignore
    return new_email


def create_admin(main_user, organization, user_model):
    roles = dict(ROLES)
    email_address = generate_email_address(organization.website, main_user.email)
    user_groups = OKTA_GROUPS_NAMES[str(ENVIRONMENT)][LAIKA_BACKEND]
    logger.info(f'Creating admin user: {email_address}')
    if user_model.objects.filter(email__iexact=email_address):
        logger.warn(f'{email_address} could not be created: already exists')
        return (None, None)
    try:
        okta_user, _ = OktaApi.create_user(
            first_name=main_user.first_name,
            last_name=main_user.last_name,
            email=email_address,
            login=email_address,
            organization=organization,
            user_groups=user_groups,
        )
        try:
            password = generate_random_password()
            OktaApi.set_user_password(okta_user.id, password)
        except Exception as e:
            logger.error('Error setting password for user: {okta_user.email}')
            logger.error(str(e))
        user_model.objects.create(
            email=email_address,
            username=okta_user.id,
            first_name=main_user.first_name,
            last_name=main_user.last_name,
            organization_id=organization.id,
            role=roles['SuperAdmin'],
        )
        return (email_address, password)
    except Exception as e:
        logger.warn(f'{email_address} could not be created: {str(e)}')
        return (None, None)


def create_admins_for_organization(organization, user_model):
    csm = organization.customer_success_manager_user
    ca = organization.compliance_architect_user
    csm_entry = None
    ca_entry = None
    if csm:
        csm_email, csm_password = create_admin(csm, organization, user_model)
    else:
        csm_email = None
        csm_password = None
    if csm_email and csm_password:
        csm_entry = create_user_entry(csm, organization, csm_email, csm_password)
    if ca:
        if ca.email != csm.email:
            ca_email, ca_password = create_admin(ca, organization, user_model)
            if ca_email and ca_password:
                ca_entry = create_user_entry(ca, organization, ca_email, ca_password)
    return (csm_entry, ca_entry)


def write_csv_row(csm_entry, ca_entry, writer):
    if csm_entry:
        writer.writerow(csm_entry)
    if ca_entry:
        writer.writerow(ca_entry)


def create_admin_accounts(apps, _):
    if ENVIRONMENT != LOCAL_ENVIRONMENT:
        Organization = apps.get_model('organization', 'organization')
        user_model = apps.get_model('user', 'user')
        if ENVIRONMENT == PROD_ENVIRONMENT:
            organizations = Organization.objects.filter(
                Q(customer_success_manager_user__isnull=False)
                | Q(compliance_architect_user_id__isnull=False)
            )
        else:
            organizations = Organization.objects.filter(
                Q(customer_success_manager_user__isnull=False)
                | Q(compliance_architect_user_id__isnull=False)
            )[:10]
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELD_NAMES)
            writer.writeheader()
            for organization in organizations:
                try:
                    logger.info(f'Creating admins for: {organization.id}')
                    csm_entry, ca_entry = create_admins_for_organization(
                        organization, user_model
                    )
                    write_csv_row(csm_entry, ca_entry, writer)
                except Exception as e:
                    logger.error(f'Failed creating admin users for {organization.name}')
                    logger.error(str(e))
        try:
            upload_file_to_s3(output_file)
        except Exception as e:
            logger.exception(f'Fail to upload file to S3 {ENVIRONMENT}-ml-report')
            logger.error(str(e))


class Migration(migrations.Migration):
    dependencies = [
        ('user', '0073_alter_user_invitation_sent'),
    ]

    operations = [migrations.RunPython(create_admin_accounts)]
