from unittest.mock import patch

import pytest
from django.test import Client

from fieldwork.models import Audit, Criteria
from user.models import User

from .mutations import UPDATE_CRITERIA
from .queries import GET_AUDITOR_ALL_CRITERIA, GET_AUDITOR_CRITERIA


@pytest.fixture
def criterias_without_audit():
    return Criteria.objects.bulk_create(
        [
            Criteria(display_id='CC1.1'),
            Criteria(display_id='A1.3'),
            Criteria(display_id='C2.1'),
            Criteria(display_id='P1.2'),
        ]
    )


@pytest.fixture
def criterias_with_audit(audit):
    return Criteria.objects.bulk_create(
        [
            Criteria(display_id='CC1.1', audit_id=audit.id),
            Criteria(display_id='A1.3', audit_id=audit.id),
            Criteria(display_id='C2.1', audit_id=audit.id),
            Criteria(display_id='P1.2', audit_id=audit.id),
        ]
    )


@pytest.mark.functional(permissions=['fieldwork.view_criteria'])
@patch(
    'auditor.schema.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_get_fieldwork_criteria(
    get_criteria_by_audit_id_mock, graphql_audit_client, audit, criteria
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_CRITERIA,
        variables={
            'auditId': audit.id,
        },
    )
    response_criteria_requirement = response['data']['auditorCriteria']['criteria']
    assert len(response_criteria_requirement) == 1


@patch(
    'auditor.schema.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
@pytest.mark.functional(permissions=['fieldwork.view_criteria'])
def test_get_all_criteria_for_criteria_with_audit(
    get_criteria_by_audit_id_mock, graphql_audit_client, audit, criterias_with_audit
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ALL_CRITERIA,
        variables={
            'auditId': audit.id,
        },
    )
    criterias = response['data']['auditorAllCriteria']
    expected_order = ['CC1.1', 'A1.3', 'C2.1', 'P1.2']
    assert len(criterias) == 4
    for index in range(len(expected_order)):
        assert criterias[index]['displayId'] == expected_order[index]
    get_criteria_by_audit_id_mock.assert_called_once()


@pytest.mark.functional(permissions=['fieldwork.view_criteria'])
@patch(
    'auditor.schema.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_get_all_criteria_for_criteria_without_audit(
    get_criteria_by_audit_id_mock, graphql_audit_client, audit, criterias_without_audit
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ALL_CRITERIA,
        variables={
            'auditId': audit.id,
        },
    )
    criterias = response['data']['auditorAllCriteria']
    expected_order = ['CC1.1', 'A1.3', 'C2.1', 'P1.2']
    for index in range(len(expected_order)):
        assert criterias[index]['displayId'] == expected_order[index]
    get_criteria_by_audit_id_mock.assert_called_once()


@pytest.mark.functional(permissions=['fieldwork.view_criteria'])
@patch(
    'auditor.schema.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_get_all_criteria_for_criteria_with_audit_and_check_default_values(
    get_criteria_by_audit_id_mock, graphql_audit_client, audit, criterias_with_audit
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ALL_CRITERIA,
        variables={
            'auditId': audit.id,
        },
    )
    criterias = response['data']['auditorAllCriteria']
    assert len(criterias) == 4
    for criteria in criterias:
        assert criteria['isQualified'] is False
    get_criteria_by_audit_id_mock.assert_called_once()


@pytest.mark.functional(permissions=['fieldwork.view_criteria'])
@patch(
    'auditor.schema.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_criteria_requirement_includes_tests(
    get_criteria_by_audit_id_mock,
    graphql_audit_client,
    audit,
    criteria_requirement,
    requirement_with_test,
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_CRITERIA,
        variables={
            'auditId': audit.id,
        },
    )
    requirements = response['data']['auditorCriteria']['criteria'][0]['requirements']
    assert len(requirements[0]['tests']) == 3


@pytest.mark.functional(permissions=["fieldwork.change_criteria"])
def test_update_criteria(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    audit_soc2_type2: Audit,
    soc2_type2_criteria: Criteria,
):
    assert (
        soc2_type2_criteria.description
        == "The entity demonstrates a commitment to integrity and ethical values."
    )
    assert soc2_type2_criteria.is_qualified is False

    new_description = "Updating criteria"

    update_criteria_input = {
        "input": dict(
            criteriaId=soc2_type2_criteria.id,
            auditId=audit_soc2_type2.id,
            fields=[
                {"field": "description", "value": new_description},
                {"field": "is_qualified", "booleanValue": True},
            ],
        )
    }

    response = graphql_audit_client.execute(
        UPDATE_CRITERIA, variables=update_criteria_input
    )

    criteria = Criteria.objects.get(
        id=soc2_type2_criteria.id, audit_id=audit_soc2_type2.id
    )

    response = response["data"]["updateAuditorCriteria"]["criteria"]
    assert response["description"] == new_description
    assert response["isQualified"] is True
    assert criteria.description == new_description
    assert criteria.is_qualified is True
