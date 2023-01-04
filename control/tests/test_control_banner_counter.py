import pytest

from certification.models import Certification, UnlockedOrganizationCertification
from control.models import Control
from control.tests.queries import CONTROL_BANNER_COUNTER
from user.models import User


@pytest.fixture(name="_users")
def fixture_users(graphql_organization):
    user_1 = User.objects.create(
        organization=graphql_organization,
        email='user1@heylaika.com',
    )
    user_2 = User.objects.create(
        organization=graphql_organization,
        email='user2@heylaika.com',
    )
    return user_1, user_2


@pytest.fixture(name="_controls")
def fixture_controls(graphql_organization):
    control_1 = Control.objects.create(
        organization=graphql_organization,
        name='Control test 1',
        implementation_notes='Implementation notes test',
    )
    control_2 = Control.objects.create(
        organization=graphql_organization,
        name='Control test 2',
    )
    control_3 = Control.objects.create(
        organization=graphql_organization, name='Control test 3'
    )
    control_4 = Control.objects.create(
        organization=graphql_organization, name='Control test 4', reference_id='XX-04'
    )
    control_5 = Control.objects.create(
        organization=graphql_organization,
        name='SOC control assigned',
        reference_id='XX-05-SOC',
    )
    control_6 = Control.objects.create(
        organization=graphql_organization,
        name='SOC Control Not assigned',
        reference_id='XX-06-SOC',
    )

    return control_1, control_2, control_3, control_4, control_5, control_6


@pytest.fixture(name="_soc_certification")
def fixture_soc_certification(graphql_organization):
    soc_certification = Certification.objects.create(
        name="SOC certification test", code="SOC"
    )

    return soc_certification


@pytest.fixture(name="unlocked_certifications")
def fixture_unlocked_certifications(graphql_organization, _soc_certification):
    unlocked_soc_certification = UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=_soc_certification
    )

    return unlocked_soc_certification


@pytest.mark.functional(permissions=['control.view_control'])
def test_control_banner_counter(
    graphql_organization, graphql_client, _controls, _users
):
    control_1, control_2, *_ = _controls
    user_1, user_2 = _users

    control_1.owner1 = user_1
    control_2.owner1 = user_2
    control_1.save()
    control_2.save()

    response = graphql_client.execute(CONTROL_BANNER_COUNTER)

    total_controls = response['data']['controlBannerCounter']['totalControls']

    assigned_controls = response['data']['controlBannerCounter']['assignedControls']

    assert total_controls == 6
    assert assigned_controls == 2


@pytest.mark.functional(permissions=['control.view_control'])
def test_control_banner_counter_no_assignees(
    graphql_organization, graphql_client, _controls
):
    response = graphql_client.execute(CONTROL_BANNER_COUNTER)

    total_controls = response['data']['controlBannerCounter']['totalControls']

    assigned_controls = response['data']['controlBannerCounter']['assignedControls']

    assert total_controls == 6
    assert assigned_controls == 0


@pytest.mark.functional(permissions=['control.view_control'])
def test_control_banner_counter_with_framework_filter(
    graphql_organization, graphql_client, _controls, _soc_certification, graphql_user
):
    _, _, _, _, control_5, _ = _controls
    control_5.owner1 = graphql_user
    control_5.save()

    response = graphql_client.execute(
        CONTROL_BANNER_COUNTER,
        variables={'filters': {'framework': _soc_certification.id}},
    )

    total_controls = response['data']['controlBannerCounter']['totalControls']

    assigned_controls = response['data']['controlBannerCounter']['assignedControls']

    assert total_controls == 2
    assert assigned_controls == 1
