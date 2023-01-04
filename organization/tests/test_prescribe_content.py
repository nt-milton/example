import os
import time

import pytest
from django.core.files import File

from blueprint.tests.test_checklist_blueprint import create_checklist
from blueprint.tests.test_object_blueprint import create_object
from blueprint.tests.test_officer_blueprint import create_officer
from blueprint.tests.test_teams_blueprint import create_team
from blueprint.tests.test_training_blueprint import create_training
from objects.models import LaikaObjectType
from organization.models import OrganizationChecklist
from organization.tasks import create_organization_seed, prescribe_default_content
from seeder.models import SeedProfile
from training.models import Training
from user.models import Officer, Team

SEED_FILE_PATH = f'{os.path.dirname(__file__)}/resources/base_profile_seed.zip'


@pytest.fixture()
def prescribe_training_mock():
    return create_training('Org Prescribe Training', 'Any description', 'Compliance')


@pytest.fixture()
def prescribe_officer_mock():
    return create_officer('Org Prescribe officer')


@pytest.fixture()
def prescribe_team_mock():
    return create_team('Org Prescribe team')


@pytest.fixture()
def prescribe_checklist_mock():
    return create_checklist(3, 'Org Prescribe checklist')


@pytest.fixture()
def prescribe_object_mock():
    return create_object('device', 1)


@pytest.mark.django_db
def test_prescribe_default_content(graphql_organization, graphql_user):
    result = prescribe_default_content.delay(
        graphql_organization.id, graphql_user.id
    ).get()

    assert result.get('success')


@pytest.mark.django_db
def test_create_organization_seed(
    graphql_organization,
    graphql_user,
    prescribe_training_mock,
    prescribe_officer_mock,
    prescribe_team_mock,
    prescribe_checklist_mock,
    prescribe_object_mock,
):
    SeedProfile.objects.create(
        name='My New Profile Template',
        default_base=True,
        file=File(name='MySeedFile', file=File(open(SEED_FILE_PATH, "rb"))),
    )

    create_organization_seed(graphql_organization, graphql_user)
    time.sleep(3)
    expected_policies_amount = 35
    expected_prescribed_items = 1

    assert (
        Training.objects.filter(organization_id=graphql_organization.id).count()
        == expected_prescribed_items
    )
    assert (
        Officer.objects.filter(organization=graphql_organization).count()
        == expected_prescribed_items
    )
    assert (
        Team.objects.filter(organization=graphql_organization).count()
        == expected_prescribed_items
    )
    assert (
        OrganizationChecklist.objects.filter(organization=graphql_organization).count()
        == expected_prescribed_items
    )
    assert (
        LaikaObjectType.objects.filter(organization=graphql_organization).count()
        == expected_prescribed_items
    )
    assert graphql_organization.policies.count() == expected_policies_amount
