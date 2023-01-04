import io
import logging
import os
import time
from copy import deepcopy
from typing import List

import boto3
from django.core.files import File

from feature.constants import DEFAULT_ORGANIZATION_FEATURE_FLAGS, okta_feature_flag
from laika.aws.cognito import delete_cognito_users
from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import (
    DJANGO_SETTINGS,
    ENVIRONMENT,
    INVITE_NO_REPLY_EMAIL,
    LAIKA_ADMIN_EMAIL,
    LAIKA_APP_ADMIN_EMAIL,
    LAIKA_WEB_REDIRECT,
    NO_REPLY_EMAIL,
)
from laika.utils.exceptions import ServiceException
from laika.utils.html import get_formatted_html
from organization.constants import (
    CONTENT_DESCRIPTION_NEW_ORG,
    FIELDS,
    HISTORY_STATUS_FAILED,
    HISTORY_STATUS_SUCCESS,
    ORG_ID,
    TDDQ_METADATA_TABLE,
    TDDQ_RESPONSES_TABLE,
    TDDQ_STRUCTURED_TABLE,
    UPLOAD_ACTION_NEW_ORG,
)
from user.constants import USER_ROLES
from user.utils.email import format_super_admin_email

from .onboarding.onboarding_content import (
    VENDOR_QUESTIONS,
    get_onboarding_vendor_names,
    vendor_names_mapper,
)

logger = logging.getLogger(__name__)
DEFAULT_TEMPLATE = 'Reports Template_2_8.html'
LOCALHOST = 'localhost'
PRODUCTION = 'prod'
hostname = LAIKA_WEB_REDIRECT


def attach_default_report_template(organization):
    current_dir = os.path.dirname(__file__)
    template_path = f'resources/{DEFAULT_TEMPLATE}'
    template_file_path = f'{current_dir}/{template_path}'
    document_file = open(template_file_path, 'r', encoding='utf-8')
    current_text = document_file.read()
    formatted_text = get_formatted_html(current_text)
    encoded_file = formatted_text.encode()

    file = File(
        name=f'template_{organization.name}.html', file=io.BytesIO(encoded_file)
    )

    from report.models import Template  # avoid circular import

    template, _ = Template.objects.get_or_create(
        name=f'template_{organization.name}',
        organization=organization,
        defaults={'file': file},
    )

    return template


@celery_app.task(name='TDDQ Execution')
def tddq_execution(formula: str):
    # Avoiding circular imports
    from .models import Organization
    from .tddq_helper import (
        get_airtable_records,
        get_formatted_data,
        update_or_create_airtable_records,
    )

    all_records = []
    responses = get_airtable_records(table_name=TDDQ_RESPONSES_TABLE, formula=formula)
    metadata = get_airtable_records(table_name=TDDQ_METADATA_TABLE, formula='')
    current_structured = get_airtable_records(TDDQ_STRUCTURED_TABLE, '')
    for response in responses:
        if (
            response.get(FIELDS, {}).get(ORG_ID)
            and Organization.objects.filter(id=response[FIELDS][ORG_ID]).exists()
        ):
            formatted_data = deepcopy(get_formatted_data(response, metadata))
            all_records.append(formatted_data)
    if len(all_records):
        update_or_create_airtable_records(current_structured, all_records)


@celery_app.task(name='Send Onboarding Review Starting Email')
def send_review_starting_email(user_emails, template_context):
    call_to_action_url = f'{DJANGO_SETTINGS.get("LAIKA_WEB_REDIRECT")}/documents'
    template_context['call_to_action_url'] = call_to_action_url
    for email in user_emails:
        logger.info(f'Sending onboarding review starting email to: {email}')
        send_email(
            subject='Review Onboarding Documentation',
            from_email=NO_REPLY_EMAIL,
            to=[email],
            template='onboarding_review_starting_email.html',
            template_context=template_context,
        )


def send_review_ready_email(user_emails):
    template_context = {
        'call_to_action_url': f'{DJANGO_SETTINGS.get("LAIKA_WEB_REDIRECT")}/onboarding'
    }

    for email in user_emails:
        logger.info(f'Sending onboarding review ready email to: {email}')
        send_email(
            subject='Your compliance playbook is ready!',
            from_email=NO_REPLY_EMAIL,
            to=[email],
            template='onboarding_review_ready_email.html',
            template_context=template_context,
        )


def send_new_organization_email_invite(subject, to, template_context):
    logger.info(f'Organization created. Sending emails to: {to}')
    send_email(
        subject=subject,
        from_email=NO_REPLY_EMAIL,
        to=to,
        template='new_organization_created.html',
        template_context=template_context,
    )


def configure_organization_initial_data(instance):
    logger.info(f'Configuring organization initial data {instance.name}')
    try:
        attach_default_report_template(instance)
    except Exception as e:
        logger.exception(f'Error attaching default template: {e}. ')
    try:
        create_organization_drive(instance)
    except Exception as e:
        logger.exception(f'Error creating organization drive: {e}. ')
    try:
        set_default_flags(instance)
    except Exception as e:
        logger.exception(f'Error setting default feature flags: {e}. ')


def create_laika_app_super_admin_user(organization):
    logger.info('Trying to create Laika App Admin')
    user, temporary_password = create_super_user_and_invite(
        organization,
        user_data={
            'email': LAIKA_APP_ADMIN_EMAIL,
            'first_name': 'laikaapp',
            'last_name': 'admin',
            'organization_id': organization.id,
        },
        should_invite=False,
    )

    send_emails_to_super_admin(user, temporary_password)


def create_csm_and_ca_user_admins(organization):
    if organization.customer_success_manager_user:
        create_super_user_and_invite(
            organization,
            {
                'email': organization.customer_success_manager_user.email,
                'first_name': organization.customer_success_manager_user.first_name,
                'last_name': organization.customer_success_manager_user.last_name,
                'organization_id': organization.id,
            },
        )

    if organization.compliance_architect_user:
        create_super_user_and_invite(
            organization,
            {
                'email': organization.compliance_architect_user.email,
                'first_name': organization.compliance_architect_user.first_name,
                'last_name': organization.compliance_architect_user.last_name,
                'organization_id': organization.id,
            },
        )


def create_super_user_and_invite(organization, user_data: dict, should_invite=True):
    from user.helpers import manage_cognito_user, manage_okta_user
    from user.models import User  # avoid circular import

    email_with_alias = format_super_admin_email(
        user_data['email'], organization.website
    )

    if User.objects.filter(email__iexact=email_with_alias):
        logger.warning(
            f'Not creating super admin user. User {email_with_alias} already '
            'exists in the organization'
        )
        return None

    logger.info(f'Creating new user {email_with_alias}')
    user = User.objects.create(
        email=email_with_alias,
        username=email_with_alias,
        first_name=user_data['first_name'],
        last_name=user_data['last_name'],
        organization_id=user_data['organization_id'],
        role=USER_ROLES['SUPER_ADMIN'],
    )

    if ENVIRONMENT == PRODUCTION:
        return manage_okta_user(user, should_invite)
    else:
        return manage_cognito_user(user, should_invite)


def create_super_admin_users(instance):
    if ENVIRONMENT == PRODUCTION:
        try:
            create_laika_app_super_admin_user(instance)
        except Exception as e:
            logger.warning(f'Error creating laika app admin user: {e}. ')

    try:
        logger.info('Trying to create ca & csm super admin users')
        create_csm_and_ca_user_admins(instance)
    except Exception as e:
        logger.warning(f'Error creating ca & csm admin users: {e}. ')


def create_organization_seed(instance, user):
    try:
        logger.info(f'Init default seeding for {instance.name}')
        prescribe_default_content.delay(instance.id, user.id)
    except Exception as e:
        logger.warning(f'Error seeding new organization. {e}. ')


def create_organization_drive(instance):
    from drive.models import Drive  # avoid circular import

    drive, _ = Drive.objects.get_or_create(organization=instance)
    logger.info(
        f'Drive with id {drive.id} created for the organization {instance.name}'
    )

    return drive


def set_default_flags(organization):
    from feature.models import Flag  # avoid circular import

    for flag in DEFAULT_ORGANIZATION_FEATURE_FLAGS.values():
        name, _, is_enabled = flag.values()
        Flag.objects.update_or_create(
            name=name,
            organization_id=organization.id,
            defaults={'is_enabled': is_enabled},
        )

    if ENVIRONMENT == PRODUCTION:
        Flag.objects.get_or_create(
            name=okta_feature_flag,
            organization=organization,
            defaults={'is_enabled': True},
        )

    logger.info(f'All default feature flags were created for {organization.name}')


def send_emails_to_super_admin(user, temporary_password):
    logger.info('Organization created. Sending emails to admins & creator')
    template_context = {
        'email': user.email,
        'temporary_password': temporary_password,
        'login_url': hostname,
    }

    if ENVIRONMENT == PRODUCTION:
        send_new_organization_email_invite(
            'Welcome to Laika!', [LAIKA_ADMIN_EMAIL], template_context
        )


def seed_base_profile(organization):
    from seeder.models import Seed, SeedProfile  # avoid circular import

    profile = SeedProfile.objects.filter(default_base=True).first()

    if profile and profile.file:
        Seed.objects.create(
            organization=organization,
            profile=profile,
            seed_file=profile.file,
            created_by=organization.created_by,
        ).run(run_async=False, should_send_alerts=False)


@celery_app.task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True,
    name='Prescribe default content',
)
def prescribe_default_content(organization_id: str, user_id):
    from organization.models import Organization
    from user.models import User

    # Doing this sleep because sometimes django returns organization not found
    time.sleep(2)
    user = User.objects.get(id=user_id)
    organization = Organization.objects.get(id=organization_id)

    try:
        prescribe_from_blueprint(organization, user)
        seed_base_profile(organization)
        return {'success': True}
    except Exception as e:
        message = f'Error prescribing for new organization: {organization_id}: {e}'
        logger.warning(message)
        create_prescription_history(organization, user, HISTORY_STATUS_FAILED)
        raise ServiceException(message)


def create_prescription_history(organization, user, status, content=''):
    from blueprint.models.history import BlueprintHistory

    new_history_entry = BlueprintHistory.objects.create(
        organization=organization,
        created_by=user,
        upload_action=UPLOAD_ACTION_NEW_ORG,
        content_description=content or CONTENT_DESCRIPTION_NEW_ORG,
        status=status,
    )
    logger.info(
        f'New blueprint history entry {new_history_entry} '
        f'for organization: {organization}'
    )


def prescribe_from_blueprint(organization, user):
    logger.info(
        f'Init prescribe content for organization: {organization} and user: {user}'
    )

    from blueprint.default_prescription.checklists import (
        prescribe as prescribe_checklists,
    )
    from blueprint.default_prescription.object_type_attributes import (
        prescribe as prescribe_attributes,
    )
    from blueprint.default_prescription.object_types import (
        prescribe as prescribe_object_types,
    )
    from blueprint.default_prescription.officers import prescribe as prescribe_officers
    from blueprint.default_prescription.questions import (
        prescribe as prescribe_questions,
    )
    from blueprint.default_prescription.teams import prescribe as prescribe_teams
    from blueprint.default_prescription.trainings import (
        prescribe as prescribe_trainings,
    )

    trainings_detail = prescribe_trainings(organization)
    officers_detail = prescribe_officers(organization)
    teams_detail = prescribe_teams(organization)
    object_types_detail = prescribe_object_types(organization)
    attributes_detail = prescribe_attributes(organization)
    checklists_detail = prescribe_checklists(organization)
    questions_detail = prescribe_questions(organization)

    error_details = (
        trainings_detail
        + officers_detail
        + teams_detail
        + object_types_detail
        + attributes_detail
        + checklists_detail
        + questions_detail
    )

    if error_details:
        create_prescription_history(
            organization=organization,
            user=user,
            status='Partial Complete',
            content='\n\n'.join(error_details),
        )
    else:
        create_prescription_history(
            organization=organization, user=user, status=HISTORY_STATUS_SUCCESS
        )


@celery_app.task(name='Delete all AWS organization data')
def delete_aws_data(organization_id):
    try:
        logger.info(f'Trying to delete S3 objects for {organization_id}')
        delete_from_boto(organization_id)
    except Exception as e:
        logger.exception(f'Error deleting organization: {organization_id}: {e}')

    logger.info(f'All S3 objects for {organization_id} were deleted successfully')

    return {'success': True}


def delete_from_boto(organization_id):
    private_prefix = f'media/private/{organization_id}/'
    bucket = boto3.resource('s3').Bucket(f'laika-app-{ENVIRONMENT}')
    bucket.objects.filter(Prefix=private_prefix).delete()
    bucket.objects.filter(Prefix=f'{organization_id}/').delete()


def delete_users_from_idp(organization):
    is_okta = organization.is_flag_active(okta_feature_flag)
    users = list(organization.users.all().values_list('email', flat=True))
    delete_users.delay(users, is_okta)


@celery_app.task(name='Delete users from idp')
def delete_users(user_emails: List[str], is_okta: bool):
    from laika.okta.api import OktaApi  # avoid circular import

    okta_api = OktaApi()

    for email in user_emails:
        if is_okta:
            okta_user = okta_api.get_user_by_email(email)
            if okta_user:
                okta_api.delete_user(okta_user.id)

        delete_cognito_users([email])

    return {'success': True}


def delete_organization_data(organization, user):
    try:
        logger.info(f'Trying to delete organization data {organization.id}')
        org_name = organization.name
        organization.delete()
        logger.info(f'Organization {org_name} deleted successfully')
    except Exception as e:
        message = f'Error deleting organization: {e}'
        logger.warning(message)
        return {'error': message}

    send_email_churned(user, org_name)


def send_email_churned(user, org_name: str):
    template_context = {
        'username': f'{user.first_name} {user.last_name}',
        'organization_name': org_name,
    }

    to = []
    if LOCALHOST not in hostname:
        to.append(LAIKA_ADMIN_EMAIL)

    send_email(
        subject='Bye Laika!',
        from_email=INVITE_NO_REPLY_EMAIL,
        to=to,
        template='organization_deleted.html',
        template_context=template_context,
    )


@celery_app.task(name='Process Organization Vendors from Onboarding Form response')
def process_organization_vendors(questionary_response, organization_id):
    from organization.models import Organization  # avoid circular import
    from vendor.models import OrganizationVendor, Vendor  # avoid circular import

    try:
        organization = Organization.objects.get(id=organization_id)

        vendor_names: list[str] = []
        for answer in questionary_response:
            vendor_names.extend(
                get_onboarding_vendor_names(
                    answer, VENDOR_QUESTIONS, vendor_names_mapper
                )
            )
        vendors = Vendor.objects.filter(name__in=vendor_names)
        logger.info(
            f'Inserting {len(vendors)} vendors in organization {organization.id}'
        )
        OrganizationVendor.objects.bulk_create(
            [
                OrganizationVendor(organization=organization, vendor_id=vendor.id)
                for vendor in vendors
            ]
        )
    except Exception as e:
        logger.warning(
            'module: organization.onboarding.tasks.process_organization_vendors Error:'
            f' {str(e)} Service message: Error processing organization vendors from'
            f' onboarding form response. organization {organization.id}.'
        )
