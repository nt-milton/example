import logging
from io import BytesIO
from typing import Optional

import requests
from django.core.files import File
from django.db.models import BooleanField, Case, Q, Value, When

from blueprint.constants import STATUS_PRESCRIBED
from blueprint.models.control import ControlBlueprint
from blueprint.types import ControlBlueprintFilterFields
from certification.models import Certification
from control.models import Control
from organization.models import OnboardingResponse
from organization.onboarding.onboarding_content import get_onboarding_contacts
from user.models import User

ONE_STATUS = 1

logger = logging.getLogger(__name__)


def blueprint_controls_search_criteria(search_criteria: str):
    return (
        Q(reference_id__icontains=search_criteria)
        | Q(name__icontains=search_criteria)
        | Q(description__icontains=search_criteria)
    )


def organization_control_reference_ids(organization_id: str):
    return list(
        Control.objects.filter(organization_id=organization_id).values_list(
            'reference_id', flat=True
        )
    )


def get_filter_blueprint_controls(filter_by: dict):
    filter_query = Q()

    for entry in filter_by:
        field = entry.get('field')
        values = entry.get('values')

        if field == ControlBlueprintFilterFields.Frameworks.value:
            filter_query.add(
                Q(
                    framework_tag__in=Certification.objects.filter(
                        id__in=values
                    ).values_list('code', flat=True)
                ),
                Q.AND,
            )

        if field == ControlBlueprintFilterFields.Families.value:
            filter_query.add(Q(family__id__in=values), Q.AND)

        if (field == ControlBlueprintFilterFields.Status.value) and len(
            values
        ) == ONE_STATUS:
            filter_by_prescribed = (True) if values[0] == STATUS_PRESCRIBED else False
            filter_query.add(Q(is_prescribed=filter_by_prescribed), Q.AND)

    return filter_query


def annotate_blueprint_controls_prescribed(organization_id):
    return ControlBlueprint.objects.annotate(
        is_prescribed=Case(
            When(
                reference_id__in=organization_control_reference_ids(organization_id),
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        )
    )


def get_attachment(attachment_field):
    for img in attachment_field:
        url = img.get('url')
        filename = img.get('filename')

        if not url or not filename:
            return ''

        try:
            response = requests.get(url)
            if not response:
                return ''

            return File(name=f'{filename}', file=BytesIO(response.content))
        except Exception as e:
            logger.warning(
                f'Error getting file from Airtable for {filename}. Exception: {e}'
            )
            return ''


def find_suggested_owner_responses(questionary_responses: dict):
    found_responses = {}
    for response in questionary_responses:
        ref = response.get('field', {}).get('ref')
        if ref == 'primary_contact_email_address':
            found_responses['primary_contact_email_address'] = response
        elif ref == 'primary_technical_contact_email_address':
            found_responses['primary_technical_contact_email_address'] = response
        elif ref == 'primary_hr_contact_email_address':
            found_responses['primary_hr_contact_email_address'] = response
    return found_responses


def get_user_or_none(response, organization_id: str) -> Optional[User]:
    if not response or (not response.get("email") and not response.get("text")):
        return None
    try:
        email = response.get("email") if response.get("email") else response.get("text")
        return User.objects.filter(
            email__iexact=email, organization__id=organization_id
        ).first()
    except User.DoesNotExist:
        logger.warning(
            f'User {response.get("email")} from response was not found. Is this'
            ' correct?'
        )
        return None


def get_suggested_users(organization_id: str) -> dict[str, Optional[User]]:
    try:
        onboarding_response = OnboardingResponse.objects.filter(
            organization__id=organization_id
        ).last()
        contacts = get_onboarding_contacts(
            onboarding_response.questionary_response, onboarding_response.submitted_by
        )

        users: dict[str, Optional[User]] = {}

        for contact in contacts:
            role = contact.get('role')
            response = {
                'email': contact.get('email_address'),
            }
            users[role] = get_user_or_none(response, organization_id)

        return users
    except Exception as e:
        logger.warning(
            'module: blueprint.prescribe.prescribe_controls'
            f' Error: {str(e)}'
            ' Service message: Error getting suggested owner.'
            f' organization {organization_id}.'
        )
        return {}
