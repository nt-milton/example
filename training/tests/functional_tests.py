import pytest

from organization.tests.factory import create_organization
from training.models import Training, TrainingAssignee
from training.tasks import send_training_reminder_email
from training.tests.mutations import CREATE_TRAINING
from user.tests import create_user


@pytest.mark.functional(permissions=['training.add_training'])
def test_create_training_mutation(graphql_client, graphql_organization):
    mocked_payload = {
        'name': 'A very important training',
        'roles': ['OrganizationAdmin'],
        'category': ['Some category'],
        'description': 'A description',
        'slides': '',
        'filename': 'A file name.pdf',
    }
    executed = graphql_client.execute(
        CREATE_TRAINING, variables={'input': mocked_payload}
    )

    result = executed['data']['createTraining']['training']['name']

    assert result is mocked_payload['name']
    assert executed['data']['createTraining']['ok'] is True


@pytest.fixture
def organization():
    return create_organization(name='Test Organization')


@pytest.mark.functional
def test_send_training_reminder_email(organization):
    user = create_user(
        organization,
        email='john@superadmin.com',
    )

    training = Training.objects.create(
        organization=organization,
        name='Test Training',
        roles=['SuperAdmin'],
        category='Asset Management',
        description='Test Description',
    )

    TrainingAssignee.objects.create(user=user, training=training)

    result = send_training_reminder_email.delay().get()
    assert result.get('success') is True
