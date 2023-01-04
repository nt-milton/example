# flake8: noqa
from datetime import datetime
from unittest.mock import patch

import pytest

from blueprint.constants import STATUS_NOT_PRESCRIBED, STATUS_PRESCRIBED
from blueprint.models.control import (
    ControlBlueprint,
    ControlCertificationSectionBlueprint,
)
from blueprint.models.control_family import ControlFamilyBlueprint
from blueprint.prescribe import prescribe_controls
from blueprint.tests.factory import create_control_blueprint
from blueprint.tests.mock_files.get_suggested_owners import get_suggested_owners
from blueprint.tests.mutations import PRESCRIBE_CONTROLS, UNPRESCRIBE_CONTROLS
from blueprint.tests.queries import (
    GET_ALL_BLUEPRINT_CONTROLS,
    GET_BLUEPRINT_CONTROL_STATUS,
    GET_BLUEPRINT_CONTROLS,
)
from certification.models import Certification
from certification.tests.factory import create_certification
from control.models import Control
from control.tests.factory import create_control, create_implementation_guide

DISPLAY_ID = 1
ONE_BLUEPRINT_CONTROL = 1
ALL_BLUEPRINT_CONTROLS = 2


@pytest.fixture
def family_blueprint() -> ControlFamilyBlueprint:
    return ControlFamilyBlueprint.objects.create(
        name='Family',
        acronym='FM1',
        description='description',
        illustration='illustration',
    )


@pytest.fixture
def control_blueprint(family_blueprint) -> ControlBlueprint:
    return ControlBlueprint.objects.create(
        reference_id='AMG-001',
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
def test_get_blueprint_controls(
    graphql_client, graphql_organization, control_blueprint
):
    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS, variables={'organizationId': graphql_organization.id}
    )
    controls = response['data']['blueprintControls']['data']
    assert len(controls) == 1
    assert controls[0]['referenceId'] == control_blueprint.reference_id


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_paginated(
    graphql_client, graphql_organization, control_blueprint
):
    fake_page = 1
    fake_page_size = 18
    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'pagination': dict(page=fake_page, pageSize=fake_page_size),
        },
    )
    controls = response['data']['blueprintControls']['data']
    pagination_response = response['data']['blueprintControls']['pagination']
    assert len(controls) == 1
    assert pagination_response['pageSize'] == fake_page_size
    assert pagination_response['page'] == fake_page


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_search_criteria_no_results(
    graphql_client, graphql_organization, control_blueprint
):
    NO_FOUND = 0
    fake_page = 1
    fake_page_size = 18
    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': str(graphql_organization.id),
            'pagination': dict(
                page=fake_page,
                pageSize=fake_page_size,
            ),
            'searchCriteria': 'this is a test that wont return results',
        },
    )
    controls = response['data']['blueprintControls']['data']
    pagination_response = response['data']['blueprintControls']['pagination']
    assert len(controls) == NO_FOUND
    assert pagination_response['pageSize'] == fake_page_size
    assert pagination_response['page'] == fake_page


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_search_criteria_results(
    graphql_client, graphql_organization, control_blueprint
):
    FOUND = 1
    fake_page = 1
    fake_page_size = 18
    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': str(graphql_organization.id),
            'pagination': dict(
                page=fake_page,
                pageSize=fake_page_size,
            ),
            'searchCriteria': 'AMG-001',
        },
    )
    controls = response['data']['blueprintControls']['data']
    pagination_response = response['data']['blueprintControls']['pagination']
    assert len(controls) == FOUND
    assert pagination_response['pageSize'] == fake_page_size
    assert pagination_response['page'] == fake_page


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_ordered(
    graphql_client, graphql_organization, family_blueprint
):
    create_control_blueprint(
        name='Aristoteles', reference_id='REF-01', family=family_blueprint
    )
    control_z = create_control_blueprint(
        name='Zulu', reference_id='REF-02', family=family_blueprint
    )
    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'orderBy': dict(field='name', order='descend'),
        },
    )
    controls = response['data']['blueprintControls']['data']
    assert len(controls) == 2
    assert controls[0]['name'] == control_z.name


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_filter_families(
    graphql_client, graphql_organization, family_blueprint
):
    control_A = create_control_blueprint(name='Aristoteles', family=family_blueprint)
    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'filter': [dict(field='families', values=[family_blueprint.id])],
        },
    )
    controls = response['data']['blueprintControls']['data']
    assert len(controls) == 1
    assert controls[0]['name'] == control_A.name
    assert controls[0]['family']['name'] == family_blueprint.name


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_filter_status_prescribed(
    graphql_client, graphql_organization, family_blueprint, control_blueprint
):
    create_control(
        graphql_organization,
        DISPLAY_ID,
        control_blueprint.name,
        control_blueprint.reference_id,
    )
    create_control_blueprint(
        name='Fake Control 2', family=family_blueprint, reference_id='AMG-002'
    )

    executed = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'filter': [dict(field='status', values=[STATUS_PRESCRIBED])],
        },
    )
    response = executed['data']['blueprintControls']['data']

    assert len(response) == ONE_BLUEPRINT_CONTROL
    assert response[0]['id'] == '1'
    assert response[0]['referenceId'] == 'AMG-001'
    assert response[0]['name'] == 'Control blueprint'
    assert response[0]['description'] == 'A description'
    assert response[0]['isPrescribed'] == True


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_filter_status_not_prescribed(
    graphql_client, graphql_organization, family_blueprint, control_blueprint
):
    create_control(
        graphql_organization,
        DISPLAY_ID,
        control_blueprint.name,
        control_blueprint.reference_id,
    )
    create_control_blueprint(
        name='Fake Control 2',
        description='Fake Description',
        family=family_blueprint,
        reference_id='AMG-002',
    )

    executed = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'filter': [dict(field='status', values=[STATUS_NOT_PRESCRIBED])],
        },
    )
    response = executed['data']['blueprintControls']['data']

    assert len(response) == ONE_BLUEPRINT_CONTROL
    assert response[0]['id'] == '2'
    assert response[0]['referenceId'] == 'AMG-002'
    assert response[0]['name'] == 'Fake Control 2'
    assert response[0]['description'] == 'Fake Description'
    assert response[0]['isPrescribed'] == False


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_filter_status_prescribe_and_not_prescribed(
    graphql_client, graphql_organization, family_blueprint, control_blueprint
):
    create_control(
        graphql_organization,
        DISPLAY_ID,
        control_blueprint.name,
        control_blueprint.reference_id,
    )
    create_control_blueprint(
        name='Fake Control 2',
        description='Fake Description',
        family=family_blueprint,
        reference_id='AMG-002',
    )

    executed = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'filter': [
                dict(field='status', values=[STATUS_PRESCRIBED, STATUS_NOT_PRESCRIBED])
            ],
        },
    )
    response = executed['data']['blueprintControls']['data']

    assert len(response) == ALL_BLUEPRINT_CONTROLS
    assert response[0]['id'] == '1'
    assert response[0]['referenceId'] == 'AMG-001'
    assert response[0]['name'] == 'Control blueprint'
    assert response[0]['description'] == 'A description'
    assert response[0]['isPrescribed'] == True
    assert response[1]['id'] == '2'
    assert response[1]['referenceId'] == 'AMG-002'
    assert response[1]['name'] == 'Fake Control 2'
    assert response[1]['description'] == 'Fake Description'
    assert response[1]['isPrescribed'] == False


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_filter_frameworks(graphql_client, graphql_organization):
    soc_2 = create_certification(graphql_organization, ['cc1'], name='SOC 2 TYPE 2')
    soc_2.code = 'SOC'
    soc_2.save()

    hipaa = create_certification(graphql_organization, ['h8'], name='HIPAA')
    hipaa.code = 'HIPAA-A'
    hipaa.save()

    control_soc = create_control_blueprint(
        name='Soc Control', reference_id='REF-01', framework_tag='SOC'
    )
    control_hipaa = create_control_blueprint(
        name='HIPAA Control', reference_id='REF-02', framework_tag='HIPAA-A'
    )

    ControlCertificationSectionBlueprint.objects.create(
        control=control_soc, certification_section=soc_2.sections.all().first()
    )

    ControlCertificationSectionBlueprint.objects.create(
        control=control_hipaa, certification_section=hipaa.sections.all().first()
    )

    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'filter': [dict(field='frameworks', values=[soc_2.id])],
        },
    )
    controls = response['data']['blueprintControls']['data']
    assert len(controls) == 1
    assert controls[0]['name'] == control_soc.name


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_controls_prescribed_or_not(
    graphql_client, graphql_organization, control_blueprint
):
    control_blueprint_2 = create_control_blueprint(
        name='Soc Control', reference_id='RF-007'
    )
    create_control(
        graphql_organization,
        1,
        control_blueprint.name,
        control_blueprint.reference_id,
    )

    response = graphql_client.execute(
        GET_BLUEPRINT_CONTROLS, variables={'organizationId': graphql_organization.id}
    )
    controls = response['data']['blueprintControls']['data']
    assert len(controls) == 2
    assert controls[0].get('referenceId') == control_blueprint.reference_id
    assert controls[0].get('isPrescribed')
    assert controls[1].get('referenceId') == control_blueprint_2.reference_id
    assert not controls[1].get('isPrescribed')


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_blueprint_control_status(graphql_client):
    executed = graphql_client.execute(GET_BLUEPRINT_CONTROL_STATUS)
    response = executed['data']['response']
    [first_item, second_item] = response['items']

    assert response['id'] == 'status'
    assert response['category'] == 'Status'
    assert first_item['id'] == 'prescribed'
    assert first_item['name'] == 'Prescribed'
    assert second_item['id'] == 'not_prescribed'
    assert second_item['name'] == 'Not Prescribed'


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_all_blueprint_controls(
    graphql_client, graphql_organization, control_blueprint
):
    response = graphql_client.execute(
        GET_ALL_BLUEPRINT_CONTROLS,
        variables={'organizationId': graphql_organization.id},
    )
    controls = response['data']['allBlueprintControls']['data']
    assert len(controls) == 1
    assert controls[0]['referenceId'] == control_blueprint.reference_id


@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_get_all_blueprint_controls_filters(
    graphql_client, graphql_organization, control_blueprint, family_blueprint
):
    control_A = create_control_blueprint(
        name='Socrates',
        family=ControlFamilyBlueprint.objects.create(name='Family Test', acronym='FT'),
    )

    response = graphql_client.execute(
        GET_ALL_BLUEPRINT_CONTROLS,
        variables={
            'organizationId': graphql_organization.id,
            'filter': [dict(field='families', values=[family_blueprint.id])],
        },
    )
    # 2 ControlBlueprint. Different families
    controls = response['data']['allBlueprintControls']['data']
    assert len(controls) == 1
    assert controls[0]['referenceId'] == control_blueprint.reference_id


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_unprescribe_controls(
    get_suggested_users_mock,
    graphql_client,
    graphql_organization,
    control_blueprint,
    onboarding_response,
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    prescribe_controls(graphql_organization.id.hex, [control_blueprint.reference_id])
    get_suggested_users_mock.assert_called_once()

    response = graphql_client.execute(
        UNPRESCRIBE_CONTROLS,
        variables={
            'organizationId': graphql_organization.id.hex,
            'controlRefIds': [control_blueprint.reference_id],
        },
    )

    org_controls = Control.objects.filter(organization_id=graphql_organization)
    request_success = response['data']['unprescribeControls']['success']

    assert 0 == org_controls.count()
    assert request_success == True


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_prescribe_controls(
    get_suggested_users_mock,
    graphql_client,
    graphql_organization,
    control_blueprint,
    onboarding_response,
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    prescribe_controls(graphql_organization.id.hex, [control_blueprint.reference_id])
    get_suggested_users_mock.assert_called_once()

    response = graphql_client.execute(
        PRESCRIBE_CONTROLS,
        variables={
            'organizationId': graphql_organization.id.hex,
            'controlReferenceIds': [control_blueprint.reference_id],
        },
    )

    org_controls = Control.objects.filter(organization_id=graphql_organization)
    request_success = response['data']['prescribeControls']['success']

    assert 1 == org_controls.count()
    assert request_success == True


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_unprescribe_controls_given_only(
    get_suggested_users_mock,
    graphql_client,
    graphql_organization,
    control_blueprint,
    family_blueprint,
    onboarding_response,
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    control_A = create_control_blueprint(
        name='Control A', reference_id='CA-01', family=family_blueprint
    )

    prescribe_controls(
        graphql_organization.id.hex,
        [control_blueprint.reference_id, control_A.reference_id],
    )
    get_suggested_users_mock.assert_called_once()

    response = graphql_client.execute(
        UNPRESCRIBE_CONTROLS,
        variables={
            'organizationId': graphql_organization.id.hex,
            'controlRefIds': [control_blueprint.reference_id],
        },
    )

    org_controls = Control.objects.filter(organization_id=graphql_organization)
    request_success = response['data']['unprescribeControls']['success']

    expected_ref_id = control_A.reference_id

    assert 1 == org_controls.count()
    assert expected_ref_id == org_controls.first().reference_id
    assert request_success == True


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.functional(permissions=['blueprint.view_controlblueprint'])
def test_unprescribe_controls_given_unexisting(
    get_suggested_users_mock,
    graphql_client,
    graphql_organization,
    control_blueprint,
    family_blueprint,
    onboarding_response,
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    control_A = create_control_blueprint(
        name='Control A', reference_id='CA-01', family=family_blueprint
    )

    prescribe_controls(
        graphql_organization.id.hex,
        [control_blueprint.reference_id, control_A.reference_id],
    )
    get_suggested_users_mock.assert_called_once()

    reference_ids = [
        control_blueprint.reference_id,
        control_A.reference_id,
        'Non-exist RefId',
    ]

    response = graphql_client.execute(
        UNPRESCRIBE_CONTROLS,
        variables={
            'organizationId': graphql_organization.id.hex,
            'controlRefIds': reference_ids,
        },
    )

    org_controls = Control.objects.filter(organization_id=graphql_organization)
    request_success = response['data']['unprescribeControls']['success']

    assert 0 == org_controls.count()
    assert request_success == True
