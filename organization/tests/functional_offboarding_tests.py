import json
from datetime import datetime

import pytest
from django.db.models import Q

from action_item.models import ActionItem
from integration.tests import create_connection_account
from objects.models import LaikaObject
from objects.system_types import USER, resolve_laika_object_type
from organization.models import (
    OffboardingStatus,
    OffboardingVendor,
    OrganizationChecklist,
    OrganizationChecklistRun,
    OrganizationChecklistRunSteps,
)
from organization.tests import create_organization
from vendor.tests.factory import create_organization_vendor, create_vendor

from ..constants import ACTION_ITEM_OFFBOARDING
from .mutations import (
    CREATE_CHECKLIST_RUN,
    CREATE_CHECKLIST_TAG,
    DELETE_CHECKLIST_STEP,
    RUN_ACCESS_SCAN,
    UPDATE_CHECKLIST_RESOURCE_MUTATION,
    UPDATE_CHECKLIST_RUN,
    UPDATE_CHECKLIST_STEP,
    USE_TEMPLATE_CHECKLIST,
)
from .queries import GET_CHECKLIST_BY_NAME, GET_OFFBOARDING_CHECKLIST


def create_checklist(organization):
    action_item = ActionItem.objects.create(
        name=ACTION_ITEM_OFFBOARDING,
        steps=[
            {
                'name': 'step 1',
                'description': 'step 1',
                'metadata': {'isTemplate': True},
            },
            {'name': 'step 2', 'description': 'step 2', 'metadata': {}},
        ],
    )
    checklist = OrganizationChecklist.objects.create(
        action_item=action_item, organization=organization
    )
    return checklist


def create_checklist_run(checklist, owner):
    return OrganizationChecklistRun.objects.create(
        checklist=checklist, owner=owner, date=datetime.today()
    )


def create_checklist_run_steps(checklist, checklist_run):
    checklist_run_steps = [
        OrganizationChecklistRunSteps(checklist_run=checklist_run, action_item=step)
        for step in checklist.action_item.steps.filter(
            Q(metadata__isTemplate__isnull=True) | Q(metadata__isTemplate=False)
        )
    ]
    OrganizationChecklistRunSteps.objects.bulk_create(checklist_run_steps)

    return OrganizationChecklistRunSteps.objects.filter(checklist_run=checklist_run)


def create_checklist_run_vendors(graphql_organization, checklist_run):
    organization_vendor = create_organization_vendor(
        graphql_organization, create_vendor()
    )
    return OffboardingVendor.objects.create(
        checklist_run=checklist_run, vendor=organization_vendor.vendor
    )


@pytest.fixture
def organization_vendor(graphql_organization):
    return create_organization_vendor(graphql_organization, create_vendor())


@pytest.fixture
def checklist(graphql_organization):
    return create_checklist(graphql_organization)


@pytest.fixture
def executed_checklist_run(graphql_client):
    executed = graphql_client.execute(
        CREATE_CHECKLIST_RUN,
        variables={
            'checklistName': ACTION_ITEM_OFFBOARDING,
            'userId': graphql_client.context['user'].id,
        },
    )
    return executed['data']['createChecklistRun']['checklistRun']


@pytest.mark.functional(permissions=['organization.view_organizationchecklist'])
def test_get_checklist_by_name(graphql_client, graphql_organization, checklist):
    checklist_name = checklist.action_item.name
    executed = graphql_client.execute(
        GET_CHECKLIST_BY_NAME, variables={'name': checklist_name}
    )

    response = executed['data']['checklist']

    assert checklist_name == response['actionItem']['name']


@pytest.mark.functional(permissions=['organization.view_organizationchecklist'])
def test_get_ofboarding_checklist(graphql_client, graphql_organization, checklist):
    action_item = checklist.action_item
    action_item.metadata = {'type': 'offboarding'}
    action_item.save()
    checklist_name = checklist.action_item.name
    executed = graphql_client.execute(GET_OFFBOARDING_CHECKLIST)

    response = executed['data']['offboarding']

    assert checklist_name == response['actionItem']['name']


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_delete_checklist_steps_for_user_organization(
    graphql_client, graphql_organization
):
    checklist_one = create_checklist(graphql_organization)

    organization_two = create_organization('My test')
    checklist_two = create_checklist(organization_two)

    ids = [
        item.id
        for item in checklist_one.action_item.steps.all().union(
            checklist_two.action_item.steps.all()
        )
    ]

    executed = graphql_client.execute(
        DELETE_CHECKLIST_STEP, variables={'checklistId': checklist_one.id, 'input': ids}
    )
    response = executed['data']['deleteChecklistStep']

    assert response['success']
    assert 1 == checklist_one.action_item.steps.all().count()
    assert 2 == checklist_two.action_item.steps.all().count()


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_add_checklist_steps_for_user_organization(
    graphql_client, graphql_organization, checklist
):
    step_description = 'add new step'
    parent_action_item = checklist.action_item.id
    executed = graphql_client.execute(
        UPDATE_CHECKLIST_STEP,
        variables={
            'parentActionItem': parent_action_item,
            'description': step_description,
            "metadata": "{\"isTemplate\":true}",
        },
    )
    response = executed['data']['updateChecklistStep']['checkListStep']

    assert 3 == ActionItem.objects.get(id=parent_action_item).steps.all().count()
    assert response['description'] == step_description


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_update_checklist_steps_for_user_organization(
    graphql_client, graphql_organization, checklist
):
    step_description = 'step updated'
    parent_action_item = checklist.action_item.id
    executed = graphql_client.execute(
        UPDATE_CHECKLIST_STEP,
        variables={
            'id': checklist.action_item.steps.last().id,
            'description': step_description,
            'parentActionItem': parent_action_item,
        },
    )
    response = executed['data']['updateChecklistStep']['checkListStep']

    assert 2 == ActionItem.objects.get(id=parent_action_item).steps.all().count()
    assert response['description'] == step_description


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_create_checklist_tag(graphql_client, graphql_organization, checklist):
    name = 'tag added'
    step_id = checklist.action_item.steps.last().id
    executed = graphql_client.execute(
        CREATE_CHECKLIST_TAG,
        variables={
            'checklistId': checklist.action_item.id,
            'name': name,
            'stepId': step_id,
        },
    )
    response = executed['data']['createChecklistTag']['tag']

    assert 1 == ActionItem.objects.filter(metadata__category__name=name).count()
    assert response['name'] == name


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_use_template_checklist_for_user_organization(
    graphql_client, graphql_organization, checklist
):
    parent_action_item = checklist.action_item.id
    executed = graphql_client.execute(
        USE_TEMPLATE_CHECKLIST,
        variables={
            'checklistId': checklist.id,
        },
    )
    response = executed['data']['useTemplateChecklist']['checklist']

    assert 2 == ActionItem.objects.get(id=parent_action_item).steps.all().count()
    assert response[0].get('name') == 'step 1'
    metadata = json.loads(response[0].get('metadata', '{}'))
    assert metadata.get('isTemplate') is False


@pytest.mark.functional(permissions=['organization.add_organizationchecklistrun'])
def test_create_checklist_run_user_organization(
    graphql_client, graphql_organization, checklist, executed_checklist_run
):
    response = executed_checklist_run
    assert (
        OrganizationChecklistRun.objects.filter(
            checklist__action_item__name=ACTION_ITEM_OFFBOARDING
        ).count()
        == 1
    )
    assert response['owner']['email'] == graphql_client.context['user'].email


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_create_checklist_run_steps_user_organization(
    graphql_client, graphql_organization
):
    checklist = create_checklist(graphql_organization)
    checklist_run = create_checklist_run(checklist, graphql_client.context['user'])
    new_date = '2021-11-01'
    new_status = 'not_applicable'
    executed = graphql_client.execute(
        UPDATE_CHECKLIST_RESOURCE_MUTATION,
        variables={
            'resourceType': 'step',
            'checklistRun': checklist_run.id,
            'status': new_status,
            'date': new_date,
            'ids': [checklist.action_item.steps.first().id],
        },
    )
    response = executed['data']['updateChecklistRunResource']['checklistResources']
    assert response[0]['date'] == new_date
    assert response[0]['status'] == OffboardingStatus.NOT_APPLICABLE


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_update_checklist_run_steps_user_organization(
    graphql_client, graphql_organization
):
    checklist = create_checklist(graphql_organization)
    checklist_run = create_checklist_run(checklist, graphql_client.context['user'])
    new_date = '2021-11-01'
    new_status = 'not_applicable'
    checklist_run_steps = create_checklist_run_steps(checklist, checklist_run)
    executed = graphql_client.execute(
        UPDATE_CHECKLIST_RESOURCE_MUTATION,
        variables={
            'resourceType': 'step',
            'checklistRun': checklist_run.id,
            'status': new_status,
            'date': new_date,
            'ids': [checklist_run_steps[0].id],
        },
    )
    response = executed['data']['updateChecklistRunResource']['checklistResources']
    assert response[0]['date'] == new_date
    assert response[0]['status'] == OffboardingStatus.NOT_APPLICABLE


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_create_checklist_run_vendors_user_organization(
    graphql_client, graphql_organization
):
    checklist = create_checklist(graphql_organization)
    checklist_run = create_checklist_run(checklist, graphql_client.context['user'])
    vendor = create_vendor()
    new_date = '2021-11-02'
    new_status = 'completed'
    executed = graphql_client.execute(
        UPDATE_CHECKLIST_RESOURCE_MUTATION,
        variables={
            'resourceType': 'vendor',
            'checklistRun': checklist_run.id,
            'status': new_status,
            'date': new_date,
            'ids': [vendor.id],
        },
    )
    response = executed['data']['updateChecklistRunResource']['checklistResources']
    assert response[0]['date'] == new_date
    assert response[0]['status'] == OffboardingStatus.COMPLETED


@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_update_checklist_run_vendors_user_organization(
    graphql_client, graphql_organization
):
    checklist = create_checklist(graphql_organization)
    checklist_run = create_checklist_run(checklist, graphql_client.context['user'])
    checklist_run_vendors = create_checklist_run_vendors(
        graphql_organization, checklist_run
    )
    new_date = '2021-11-04'
    executed = graphql_client.execute(
        UPDATE_CHECKLIST_RESOURCE_MUTATION,
        variables={
            'resourceType': 'vendor',
            'checklistRun': checklist_run.id,
            'date': new_date,
            'ids': [checklist_run_vendors.id],
        },
    )
    response = executed['data']['updateChecklistRunResource']['checklistResources']
    assert response[0]['date'] == new_date
    assert response[0]['status'] == OffboardingStatus.PENDING


@pytest.mark.functional(permissions=['organization.add_organizationchecklistrun'])
def test_resolve_checklist_non_integrated_vendors(
    graphql_client,
    graphql_organization,
    checklist,
    organization_vendor,
    executed_checklist_run,
):
    response = executed_checklist_run

    assert 1 == len(response['offboardingRun']['nonIntegratedVendors'])


@pytest.mark.functional(permissions=['organization.change_organizationchecklistrun'])
def test_update_checklist_run(graphql_client, graphql_organization):
    # ARRANGE
    checklist = create_checklist(graphql_organization)
    checklist_run = create_checklist_run(checklist, graphql_client.context['user'])
    new_date = "2021-11-01"

    # ACT
    executed = graphql_client.execute(
        UPDATE_CHECKLIST_RUN,
        variables={
            "checklistRunId": checklist_run.id,
            "date": "2021-11-01",
            "metadata": json.dumps({"terminationType": "Voluntary"}),
        },
    )
    response = executed['data']['updateChecklistRun']['checklistRun']
    metadata = json.loads(response['metadata'])

    # ASSERT
    assert response['date'] == new_date
    assert 'Voluntary' == metadata['terminationType']


@pytest.mark.skip(reason="It is failing")
@pytest.mark.functional(permissions=['organization.change_organizationchecklist'])
def test_run_access_scan(graphql_client, graphql_organization):
    # Arrange
    checklist = create_checklist(graphql_organization)
    checklist_run = create_checklist_run(checklist, graphql_client.context['user'])
    connection_account = create_connection_account(
        'AWS', organization=graphql_organization
    )
    vendor = connection_account.integration.vendor
    lo_type = resolve_laika_object_type(graphql_organization, USER)
    LaikaObject.objects.create(
        object_type=lo_type,
        data={'Email': checklist_run.owner.email},
        connection_account=connection_account,
    )

    # Act
    executed = graphql_client.execute(
        RUN_ACCESS_SCAN,
        variables={'userId': checklist_run.owner.id, 'vendorIds': [vendor.id]},
    )
    updated_checklist = OrganizationChecklistRun.objects.get(id=checklist_run.id)
    response = executed['data']['runAccessScan']['success']
    assert response is True
    assert updated_checklist.metadata['runningScan'] is True
    assert updated_checklist.metadata['vendorIds'] == [vendor.id]
