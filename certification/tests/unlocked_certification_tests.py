import datetime
import logging

import pytest

from certification.models import UnlockedOrganizationCertification
from certification.tests.factory import create_certification
from certification.tests.mutations import (
    UPDATE_AUDIT_COMPLETION_DATE,
    UPDATE_AUDIT_DATES_UNLOCKED_CERTIFICATION,
)
from organization.tests import create_organization

logger = logging.getLogger(__name__)

SIMPLE_DATE_FORMAT = '%Y-%m-%d'


@pytest.fixture
def organization():
    return create_organization(name='Laika Dev')


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_update_audit_dates_unlocked_certification(graphql_client, organization):
    expected_start_date_string = '2022-10-10'
    expected_start_date = datetime.datetime.strptime(
        expected_start_date_string, SIMPLE_DATE_FORMAT
    )
    certification = create_certification(organization=organization)

    unlocked_certification = UnlockedOrganizationCertification.objects.get(
        organization=organization, certification=certification
    )

    update_unlocked_cert_input = {
        'input': dict(
            organizationId=str(unlocked_certification.organization_id),
            certificationId=str(unlocked_certification.certification_id),
            targetAuditStartDate=expected_start_date_string,
            targetAuditCompletionDate=expected_start_date_string,
        )
    }
    response = graphql_client.execute(
        UPDATE_AUDIT_DATES_UNLOCKED_CERTIFICATION, variables=update_unlocked_cert_input
    )
    assert len(response) == 1
    unlocked_cert = UnlockedOrganizationCertification.objects.get(
        organization__id=unlocked_certification.organization.id,
        certification__id=unlocked_certification.certification.id,
    )
    assert unlocked_cert.target_audit_start_date.strftime(
        SIMPLE_DATE_FORMAT
    ) == expected_start_date.strftime(SIMPLE_DATE_FORMAT)


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_audit_completion_date(graphql_client, organization):
    expected_completion_date_string = '2022-11-10'
    expected_completion_date = datetime.datetime.strptime(
        expected_completion_date_string, SIMPLE_DATE_FORMAT
    )
    certification = create_certification(organization=organization)

    unlocked_certification = UnlockedOrganizationCertification.objects.get(
        organization=organization, certification=certification
    )

    update_completion_date_input = {
        'input': dict(
            organizationId=str(unlocked_certification.organization_id),
            certificationId=str(unlocked_certification.certification_id),
            targetAuditCompletionDate=expected_completion_date_string,
        )
    }
    response = graphql_client.execute(
        UPDATE_AUDIT_COMPLETION_DATE, variables=update_completion_date_input
    )
    assert (
        response['data']['updateAuditCompletionDate']['unlockedOrgCertification']['id']
        == '1'
    )
    unlocked_cert = UnlockedOrganizationCertification.objects.get(
        organization__id=unlocked_certification.organization.id,
        certification__id=unlocked_certification.certification.id,
    )
    assert unlocked_cert.target_audit_completion_date.strftime(
        SIMPLE_DATE_FORMAT
    ) == expected_completion_date.strftime(SIMPLE_DATE_FORMAT)
