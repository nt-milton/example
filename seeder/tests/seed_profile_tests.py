import os

import pytest
from django.core.files import File

from certification.tests.queries import GET_SEED_PROFILES
from seeder.models import SeedProfile
from seeder.tests import create_seed_profiles

template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.zip'


@pytest.mark.django_db
def test_seed_profile_is_visible_field():
    file_to_seed = File(open(template_seed_file_path, 'rb'))
    seed_profile = SeedProfile.objects.create(
        name='[Playbooks] HIPAA Documents',
        content_description='Playbooks related document templates specific to HIPAA.',
        file=file_to_seed,
    )
    assert not seed_profile.is_visible


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_seed_profiles(graphql_client):
    create_seed_profiles()
    executed = graphql_client.execute(GET_SEED_PROFILES)

    response = executed['data']['seedProfiles']
    total_seed_profiles = 1

    assert len(response) == total_seed_profiles
