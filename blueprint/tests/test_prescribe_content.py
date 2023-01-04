from datetime import datetime
from unittest.mock import patch

import pytest

from blueprint.models import ControlBlueprint, ControlFamilyBlueprint
from blueprint.mutations import prescribe_content
from blueprint.tests.mock_files.get_suggested_owners import get_suggested_owners
from certification.models import Certification, UnlockedOrganizationCertification
from control.models import Control
from control.tests.factory import create_implementation_guide

SOC_TAG = 'SOC'

PRESCRIBE_CONTENT = '''
  mutation PrescribeContent(
    $organizationId: String!
    $frameworkTags: [String]!
  ) {
    prescribeContent(
      organizationId: $organizationId
      frameworkTags: $frameworkTags
    ) {
      success
    }
  }
'''


def create_control_blueprint():
    family_blueprint = ControlFamilyBlueprint.objects.create(
        name='Family',
        acronym='FM1',
        description='description',
        illustration='illustration',
    )

    ControlBlueprint.objects.create(
        reference_id='AMG-001-SOC',
        household='AMG-001',
        name='Control blueprint',
        description='A description',
        family=family_blueprint,
        implementation_guide=create_implementation_guide(
            name='New Implementation Guide', description='Any description'
        ),
        updated_at=datetime.strptime(
            '2022-03-02T22:20:15.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
        ),
    )


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_prescribe_content(graphql_client, graphql_organization):
    response = graphql_client.execute(
        PRESCRIBE_CONTENT,
        variables={
            'organizationId': graphql_organization.id,
            'frameworkTags': [SOC_TAG, 'ISO'],
        },
    )

    assert response['data']['prescribeContent']['success']


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.django_db
def test_prescribe_content_celery(
    get_suggested_users_mock, graphql_organization, graphql_user
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    Certification.objects.create(name='SOC 2 Security', code=SOC_TAG)
    create_control_blueprint()

    prescribe_content(graphql_user.id, graphql_organization.id, [SOC_TAG])
    get_suggested_users_mock.assert_called_once()

    org_controls = Control.objects.filter(organization_id=graphql_organization.id)
    assert 1 == org_controls.count()
    assert (
        UnlockedOrganizationCertification.objects.filter(
            certification__code=SOC_TAG
        ).count()
        == 1
    )
