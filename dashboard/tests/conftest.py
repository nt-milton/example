from datetime import datetime, timedelta

import pytest

from action_item.models import ActionItem, ActionItemStatus
from certification.models import CertificationSection
from certification.tests.factory import create_certification
from control.constants import STATUS
from control.tests.factory import create_control
from dashboard.models import ActionItem as DashboardActionItem
from dashboard.tests.factory import (
    create_dashboard_action_item,
    create_subtask,
    create_subtask_action_item,
    create_task_view_action_item,
)
from feature.constants import new_controls_feature_flag
from feature.models import Flag
from organization.tests import create_organization
from program.tests import create_task
from user.constants import ALERT_PREFERENCES, EMAIL_PREFERENCES
from user.tests import create_user

ACTION_ITEM_DESCRIPTION = 'test description'

NOT_STARTED = 'not_started'
COMPLETED = 'completed'

CONTROL_TYPE = 'control'
ACCESS_REVIEW_TYPE = 'access_review'
POLICY_TYPE = 'policy'
QUICK_START_TYPE = 'quick_start'
MONITOR_TYPE = 'monitor'
PLAYBOOK_TYPE = 'playbook_task'


@pytest.fixture()
def new_controls_flag(graphql_organization):
    Flag.objects.get_or_create(
        name=new_controls_feature_flag,
        organization=graphql_organization,
        defaults={'is_enabled': True},
    )


@pytest.fixture()
def pending_subtask_weekly(graphql_organization, user_weekly, task):
    create_subtask(user_weekly, task)
    DashboardActionItem.objects.create(
        organization=graphql_organization,
        assignee=user_weekly,
        status=NOT_STARTED,
        due_date=datetime.now() + timedelta(days=5),
        description=ACTION_ITEM_DESCRIPTION,
        sort_index=1,
    )


@pytest.fixture()
def completed_subtask_weekly(graphql_organization, user_weekly, task):
    subtask = create_subtask(user_weekly, task)
    create_subtask_action_item(
        graphql_organization,
        subtask,
        user_weekly,
        ACTION_ITEM_DESCRIPTION,
        COMPLETED,
    )


@pytest.fixture()
def pending_subtask_daily(graphql_organization, user_daily, task):
    create_subtask(user_daily, task)
    subtask = create_subtask(user_daily, task)
    create_subtask_action_item(
        graphql_organization, subtask, user_daily, ACTION_ITEM_DESCRIPTION, NOT_STARTED
    )


@pytest.fixture()
def completed_subtask_daily(graphql_organization, user_daily, task):
    subtask = create_subtask(user_daily, task)
    create_subtask_action_item(
        graphql_organization, subtask, user_daily, ACTION_ITEM_DESCRIPTION, COMPLETED
    )


@pytest.fixture()
def no_action_items_subtask(graphql_organization, user_daily, task):
    create_subtask(user_daily, task)


@pytest.fixture()
def task(graphql_organization):
    return create_task(organization=graphql_organization)


@pytest.fixture()
def user_daily(graphql_organization):
    return create_user(
        graphql_organization,
        [],
        'laika@heylaika.com',
        {
            "profile": {
                "alerts": ALERT_PREFERENCES['NEVER'],
                "emails": EMAIL_PREFERENCES['DAILY'],
            }
        },
    )


@pytest.fixture()
def user_weekly(graphql_organization):
    user = create_user(
        graphql_organization,
        [],
        'laika@heylaika.com',
        {
            "profile": {
                "alerts": ALERT_PREFERENCES['NEVER'],
                "emails": EMAIL_PREFERENCES['WEEKLY'],
            }
        },
    )
    return user


# dashboard views fixtures
@pytest.fixture()
def task_view_action_items_from_all_types(graphql_user, graphql_organization):
    create_task_view_action_item(
        unique_action_item_id='control-action-item-1',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=CONTROL_TYPE,
        reference_id='AC-001-SOC',
    )
    create_task_view_action_item(
        unique_action_item_id='control-action-item-2',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=CONTROL_TYPE,
        reference_id='AC-002-SOC',
    )
    create_task_view_action_item(
        unique_action_item_id='control-action-item-3',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=CONTROL_TYPE,
        reference_id='AC-006-ISO',
    )
    create_task_view_action_item(
        unique_action_item_id='control-action-item-4',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=CONTROL_TYPE,
        reference_id='AC-002-SOC-C',
    )
    create_task_view_action_item(
        unique_action_item_id='policy-action-item-1',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=POLICY_TYPE,
        reference_id='',
    )
    create_task_view_action_item(
        unique_action_item_id='quick-start-action-item-1',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=QUICK_START_TYPE,
        reference_id='',
    )
    # completed action items
    create_task_view_action_item(
        unique_action_item_id='control-action-item-5',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.COMPLETED.value,
        type=CONTROL_TYPE,
        reference_id='AC-002-SOC-C',
    )
    create_task_view_action_item(
        unique_action_item_id='quick-start-action-item-2',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.COMPLETED.value,
        type=QUICK_START_TYPE,
        reference_id='',
    )
    create_task_view_action_item(
        unique_action_item_id='access-review-action-item-1',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.COMPLETED.value,
        type=ACCESS_REVIEW_TYPE,
        reference_id='',
    )


@pytest.fixture()
def action_items_from_all_types(graphql_user, graphql_organization):
    create_dashboard_action_item(
        unique_action_item_id='324dh-sadf54f',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=POLICY_TYPE,
        reference_id='',
    )
    create_dashboard_action_item(
        unique_action_item_id='3sdfg34gv56fh-sadf54f',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.NEW.value,
        type=QUICK_START_TYPE,
        reference_id='',
    )
    # completed action items
    create_dashboard_action_item(
        unique_action_item_id='67hg7tujfg456ytr-sadf54f',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.COMPLETED.value,
        type=QUICK_START_TYPE,
    )
    create_dashboard_action_item(
        unique_action_item_id='access-review-action-item-1',
        user=graphql_user,
        organization=graphql_organization,
        description=ACTION_ITEM_DESCRIPTION,
        status=ActionItemStatus.COMPLETED.value,
        type=ACCESS_REVIEW_TYPE,
    )


# framework cards fixtures
@pytest.fixture()
def framework_with_not_implemented_controls(graphql_organization):
    soc2_sections = ['CC1.3', 'CC2.2']
    # Org 2 - validate edge case where:
    # control in different organizations share certification sections
    org2 = create_organization()
    create_certification(
        graphql_organization,
        soc2_sections,
        name='SOC 2 Type 1',
        unlock_certificate=True,
        code='SOC',
    )
    not_implemented_control_1 = create_control(
        organization=graphql_organization,
        display_id='2',
        name='Not Implemented Control 1',
        status=STATUS['NOT IMPLEMENTED'],
        reference_id='XR-001-SOC',
    )
    not_implemented_control_2 = create_control(
        organization=graphql_organization,
        display_id='3',
        name='Not Implemented Control 2',
        status=STATUS['NOT IMPLEMENTED'],
        reference_id='AC-001-SOC',
    )
    control_from_other_organization = create_control(
        organization=org2,
        display_id='3',
        name='Implemented Control 1',
        status=STATUS['IMPLEMENTED'],
        reference_id='PR-001-SOC',
    )
    not_implemented_control_1.certification_sections.add(
        CertificationSection.objects.get(name=soc2_sections[0])
    )
    not_implemented_control_2.certification_sections.add(
        CertificationSection.objects.get(name=soc2_sections[0]),
        CertificationSection.objects.get(name=soc2_sections[1]),
    )
    control_from_other_organization.certification_sections.add(
        CertificationSection.objects.get(name=soc2_sections[0])
    )


@pytest.fixture()
def framework_with_implemented_controls(graphql_organization, new_controls_flag):
    # Org 2 - validate edge case where:
    # control in different organizations share certification sections
    org2 = create_organization()
    soc2_sections = ['CC1.1', 'CC2.2', 'CC4.1', 'CC6.2', 'CC8.1', 'CC2.0']
    iso_sections = ['IS1.1', 'IS2.2', 'IS4.1', 'IS6.2', 'IS8.1', 'IS2.0']
    create_certification(
        graphql_organization,
        iso_sections,
        name='ISO 27001 (2013)',
        unlock_certificate=True,
        code='ISO',
    )
    create_certification(
        graphql_organization,
        soc2_sections,
        name='SOC 2 Security',
        unlock_certificate=True,
        code='SOC',
    )
    # Create controls
    operational_control = create_control(
        organization=graphql_organization,
        display_id='1',
        name='Operational Control 1',
        status=STATUS['IMPLEMENTED'],
        reference_id="AMG-002-SOC",
    )
    needs_attention_control = create_control(
        organization=graphql_organization,
        display_id='2',
        name='Flagged Control 1',
        status=STATUS['IMPLEMENTED'],
        reference_id="AMG-001-SOC",
    )
    not_implemented_control_1 = create_control(
        organization=graphql_organization,
        display_id='3',
        name='Not Implemented Control 1',
        status=STATUS['NOT IMPLEMENTED'],
        reference_id="AMG-003-SOC",
    )
    not_implemented_control_2 = create_control(
        organization=graphql_organization,
        display_id='4',
        name='Not Implemented Control 2',
        status=STATUS['NOT IMPLEMENTED'],
        reference_id="AMG-004-SOC",
    )
    not_implemented_control_3 = create_control(
        organization=graphql_organization,
        display_id='4',
        name='Not Implemented Control 2',
        status=STATUS['NOT IMPLEMENTED'],
        reference_id="AMG-001-ISO",
    )
    control_from_other_organization = create_control(
        organization=org2,
        display_id='3',
        name='Implemented Control 1',
        status=STATUS['IMPLEMENTED'],
    )
    # Create action items
    out_of_date_action_item = ActionItem.objects.create(
        name='LAI-001',
        status=ActionItemStatus.NEW,
        due_date=datetime.now() - timedelta(days=5),
        description=ACTION_ITEM_DESCRIPTION,
    )
    required_action_item_completed = ActionItem.objects.create(
        name='Required-Action-Item-001',
        is_required=True,
        status=ActionItemStatus.COMPLETED,
        due_date=datetime.now() - timedelta(days=5),
    )
    required_action_item_completed_2 = ActionItem.objects.create(
        name='Required-Action-Item-002',
        is_required=True,
        status=ActionItemStatus.COMPLETED,
        due_date=datetime.now() - timedelta(days=5),
    )
    required_action_item_3 = ActionItem.objects.create(
        name='Required-Action-Item-003',
        is_required=True,
        status=ActionItemStatus.NEW,
        due_date=datetime.now() - timedelta(days=5),
    )
    required_action_item_not_applicable = ActionItem.objects.create(
        name='Required-Action-Item-004',
        is_required=True,
        status=ActionItemStatus.NOT_APPLICABLE,
        due_date=datetime.now() - timedelta(days=5),
    )
    # Add certification sections
    needs_attention_control.certification_sections.add(
        CertificationSection.objects.get(name=soc2_sections[0])
    )
    operational_control.certification_sections.add(
        CertificationSection.objects.get(name=soc2_sections[1])
    )
    not_implemented_control_1.certification_sections.add(
        *CertificationSection.objects.filter(name__in=soc2_sections[:4])
    )
    not_implemented_control_2.certification_sections.add(
        *CertificationSection.objects.filter(name__in=soc2_sections[:4])
    )
    not_implemented_control_3.certification_sections.add(
        *CertificationSection.objects.filter(name__in=soc2_sections[:4])
    )
    not_implemented_control_3.certification_sections.add(
        *CertificationSection.objects.filter(name__in=iso_sections[:4])
    )
    control_from_other_organization.certification_sections.add(
        CertificationSection.objects.get(name=soc2_sections[0])
    )
    # Add action items
    control_from_other_organization.action_items.add(required_action_item_completed)
    not_implemented_control_1.action_items.add(required_action_item_completed_2)
    not_implemented_control_2.action_items.add(required_action_item_3)
    not_implemented_control_3.action_items.add(required_action_item_not_applicable)
    needs_attention_control.action_items.add(out_of_date_action_item)
