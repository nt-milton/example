from unittest.mock import patch

import pytest

from blueprint.default_prescription.checklists import prescribe as prescribe_checklists
from blueprint.default_prescription.object_type_attributes import (
    prescribe as prescribe_object_type_attributes,
)
from blueprint.default_prescription.object_types import (
    prescribe as prescribe_object_types,
)
from blueprint.default_prescription.officers import prescribe as prescribe_officers
from blueprint.default_prescription.questions import prescribe as prescribe_questions
from blueprint.default_prescription.teams import prescribe as prescribe_teams
from blueprint.default_prescription.trainings import prescribe as prescribe_trainings
from blueprint.tests.test_checklist_blueprint import create_checklist
from blueprint.tests.test_object_attribute_blueprint import create_object_attribute
from blueprint.tests.test_object_blueprint import create_object
from blueprint.tests.test_officer_blueprint import create_officer
from blueprint.tests.test_questions_blueprint import create_question
from blueprint.tests.test_teams_blueprint import create_team
from blueprint.tests.test_training_blueprint import create_training
from library.models import Question, Questionnaire
from objects.models import Attribute, LaikaObjectType
from organization.models import OrganizationChecklist
from training.models import Training
from user.models import Officer, Team


@pytest.fixture()
def first_training_mock():
    return create_training(
        'New Training 001', 'Training description - 001', 'Compliance'
    )


@pytest.fixture()
def officer_mock():
    return create_officer('New officer 001')


@pytest.fixture()
def team_mock():
    return create_team('New team 001')


@pytest.fixture()
def checklist_mock():
    return create_checklist(3, 'New checklist 001')


@pytest.fixture()
def object_mock():
    return create_object('device', 1)


@pytest.fixture()
def object_attribute_mock():
    return create_object_attribute('1', 'New object attribute 001', 1)


@pytest.fixture()
def question_mock():
    return create_question('New Question 001')


@pytest.fixture()
def question_mock_2():
    return create_question('New Question 002')


@pytest.mark.django_db
def test_prescribe_trainings_unit(graphql_organization, first_training_mock):
    status_detail = prescribe_trainings(graphql_organization)
    assert not status_detail
    assert Training.objects.count() == 1
    assert Training.objects.get(name='New Training 001')


@pytest.mark.django_db
def test_prescribe_training_error(graphql_organization):
    with patch('blueprint.default_prescription.trainings.prescribe') as mock:
        assert mock
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(Exception):
            status_detail = prescribe_trainings(graphql_organization)
            assert status_detail
            assert Training.objects.count() == 0


@pytest.mark.django_db
def test_prescribe_officers_unit(graphql_organization, officer_mock):
    status_detail = prescribe_officers(graphql_organization)
    assert not status_detail
    assert Officer.objects.count() == 1
    assert Officer.objects.get(name='New officer 001')


@pytest.mark.django_db
def test_prescribe_officers_error(graphql_organization):
    with patch('blueprint.default_prescription.officers.prescribe') as mock:
        assert mock
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(Exception):
            status_detail = prescribe_officers(graphql_organization)
            assert status_detail
            assert not Officer.objects.count()


@pytest.mark.django_db
def test_prescribe_teams_unit(graphql_organization, team_mock):
    status_detail = prescribe_teams(graphql_organization)
    assert not status_detail
    assert Team.objects.count() == 1
    assert Team.objects.get(name='New team 001')


@pytest.mark.django_db
def test_prescribe_teams_error(graphql_organization):
    with patch('blueprint.default_prescription.teams.prescribe') as mock:
        assert mock
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(Exception):
            status_detail = prescribe_officers(graphql_organization)
            assert status_detail
            assert not Team.objects.count()


@pytest.mark.django_db
def test_prescribe_checklists_unit(graphql_organization, checklist_mock):
    status_detail = prescribe_checklists(graphql_organization)
    assert not status_detail
    assert OrganizationChecklist.objects.count() == 1


@pytest.mark.django_db
def test_prescribe_checklists_error(graphql_organization):
    with patch('blueprint.default_prescription.checklists.prescribe') as mock:
        assert mock
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(Exception):
            status_detail = prescribe_checklists(graphql_organization)
            assert status_detail
            assert not OrganizationChecklist.objects.count()


@pytest.mark.django_db
def test_prescribe_object_types_unit(graphql_organization, object_mock):
    status_detail = prescribe_object_types(graphql_organization)
    assert not status_detail
    assert LaikaObjectType.objects.count() == 1
    assert LaikaObjectType.objects.get(display_name='device')


@pytest.mark.django_db
def test_prescribe_object_types_error(graphql_organization):
    with patch('blueprint.default_prescription.object_types.prescribe') as mock:
        assert mock
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(Exception):
            status_detail = prescribe_object_types(graphql_organization)
            assert status_detail
            assert not LaikaObjectType.objects.count()


@pytest.mark.django_db
def test_prescribe_object_type_attributes_unit(
    graphql_organization, object_mock, object_attribute_mock
):
    status_detail = prescribe_object_types(graphql_organization)
    attr_status_detail = prescribe_object_type_attributes(graphql_organization)

    assert not status_detail
    assert not attr_status_detail
    assert Attribute.objects.count() == 1
    assert Attribute.objects.get(name='New object attribute 001')


@pytest.mark.django_db
def test_prescribe_object_type_attributes_error(graphql_organization):
    with patch(
        'blueprint.default_prescription.object_type_attributes.prescribe'
    ) as mock:
        assert mock
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(Exception):
            status_detail = prescribe_object_type_attributes(graphql_organization)
            assert status_detail
            assert not Attribute.objects.count()


@pytest.mark.django_db
def test_prescribe_questions(graphql_organization, question_mock, question_mock_2):
    status_detail = prescribe_questions(graphql_organization)
    assert not status_detail
    assert Questionnaire.objects.count() == 1
    assert Question.objects.count() == 2
    assert Question.objects.get(text='New Question 001')
    assert Question.objects.get(text='New Question 002')


@pytest.mark.django_db
def test_prescribe_questions_error(graphql_organization):
    with patch('blueprint.default_prescription.questions.prescribe') as mock:
        assert mock
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(Exception):
            status_detail = prescribe_questions(graphql_organization)
            assert status_detail
            assert not Question.objects.count()
            assert not Questionnaire.objects.count()
