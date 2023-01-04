from unittest.mock import patch

import pytest

from seeder.tasks import seed_profiles_to_organization
from seeder.tests import create_seed_profiles

SEED_ORGANIZATION = '''
  mutation SeedOrganization(
    $organizationId: String!
    $profileIds: [String]!
  ) {
    seedOrganization(
      organizationId: $organizationId
      profileIds: $profileIds
    ) {
      success
    }
  }
'''


@pytest.mark.functional(permissions=['user.view_concierge'])
@patch('seeder.tasks.send_alerts', return_value=True)
def test_seed_organization(send_alerts_mock, graphql_client, graphql_organization):
    profiles = create_seed_profiles()
    response = graphql_client.execute(
        SEED_ORGANIZATION,
        variables={
            'organizationId': graphql_organization.id,
            'profileIds': [profiles[0].id, profiles[1].id],
        },
    )

    assert send_alerts_mock.called
    assert send_alerts_mock.call_count == 2
    assert response['data']['seedOrganization']['success']


@pytest.mark.functional(permissions=['user.view_concierge'])
@patch('seeder.tasks.send_alerts', return_value=True)
def test_seed_organization_celery(send_alerts_mock, graphql_organization, graphql_user):
    profiles = create_seed_profiles()

    result = seed_profiles_to_organization.delay(
        graphql_user.id, graphql_organization.id, [profiles[0].id, profiles[1].id]
    ).get()

    assert result
    assert send_alerts_mock.called
    assert send_alerts_mock.call_count == 2
