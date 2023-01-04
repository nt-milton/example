import datetime
import os
import tempfile
from typing import List

import pytest
import pytz
from django.core.files import File

from action_item.models import ActionItem
from audit.models import Audit, AuditFrameworkType
from audit.tests.factory import get_framework_key_from_value
from certification.models import (
    ArchivedUnlockedOrganizationCertification,
    Certification,
    UnlockedOrganizationCertification,
)
from control.constants import (
    COMPLETED,
    MAPPING_PROFILE_ZIP_NAME,
    SEED_PROFILE_NAME,
    STATUS,
    MetadataFields,
)
from control.models import Control
from control.mutations import (
    apply_seeders,
    archive_old_certifications,
    migrate_organization,
    unlock_frameworks,
)
from control.tests.factory import create_action_item
from control.tests.mutations import MIGRATE_ORGANIZATION_TO_MY_COMPLIANCE
from control.tests.queries import GET_MIGRATION_HISTORY
from coupon.models import Coupon
from evidence.constants import FILE
from evidence.models import Evidence
from feature.constants import (
    new_controls_feature_flag,
    playbooks_feature_flag,
    read_only_playbooks_feature_flag,
)
from feature.models import Flag
from organization.models import Organization
from program.models import Program, SubTask, Task
from seeder.models import MyComplianceMigration, SeedProfile
from tag.models import Tag
from user.models import User

mapping_file_path = f'{os.path.dirname(__file__)}/resources/{MAPPING_PROFILE_ZIP_NAME}'

TESTING_FRAMEWORKS = ['SOC 1', 'SOC 2 Security']


@pytest.fixture(autouse=True)
def set_up_test():
    mapping_file = File(open(mapping_file_path, "rb"))
    SeedProfile.objects.create(
        name=SEED_PROFILE_NAME,
        file=File(name=MAPPING_PROFILE_ZIP_NAME, file=mapping_file),
    )


@pytest.fixture(name="_new_controls_flag")
def fixture_new_controls_flag(graphql_organization):
    Flag.objects.get_or_create(
        name=new_controls_feature_flag,
        organization=graphql_organization,
        defaults={'is_enabled': True},
    )


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


@pytest.fixture(name="_program")
def program(graphql_organization):
    return Program.objects.create(
        organization=graphql_organization, name='Program', description='Test Program'
    )


@pytest.fixture(name="_task")
def fixture_task(graphql_organization, _program):
    return Task.objects.create(name='Task', description='Test Task', program=_program)


@pytest.fixture(name="_evidence")
def fixture_evidence(graphql_organization):
    file_name = 'Evidence'
    return Evidence.objects.create(
        name=file_name,
        description='test evidence',
        organization=graphql_organization,
        type=FILE,
        file=File(file=tempfile.TemporaryFile(), name=file_name),
    )


@pytest.fixture(name="_subtasks")
def fixture_subtasks(_users, _task, _evidence, graphql_organization):
    user_1, _ = _users
    subtask_a = SubTask.objects.create(
        task=_task,
        text='Text subtask a',
        group='policy',
        due_date=datetime.date.today(),
        status='not_started',
        assignee=user_1,
        completed_on=datetime.date.today(),
        migration_id='1',
    )
    subtask_b = SubTask.objects.create(
        task=_task,
        text='Text subtask b',
        group='policy',
        due_date=datetime.date.today(),
        status='not_started',
        assignee=user_1,
        migration_id='2',
    )
    subtask_c = SubTask.objects.create(
        task=_task,
        text='Text subtask c',
        group='policy',
        due_date=datetime.date.today(),
        status='not_started',
        assignee=user_1,
        migration_id='3',
    )
    subtask_d = SubTask.objects.create(
        task=_task,
        text='Text subtask that does not match',
        group='policy',
        migration_id='0',
    )
    subtask_e = SubTask.objects.create(
        task=_task, text='Text subtask e', group='policy', migration_id='5'
    )

    _evidence.system_tags.add(
        Tag.objects.create(name=subtask_a.id, organization=graphql_organization)
    )
    _evidence.system_tags.add(
        Tag.objects.create(name=subtask_b.id, organization=graphql_organization)
    )
    _evidence.system_tags.add(
        Tag.objects.create(name=subtask_c.id, organization=graphql_organization)
    )

    return subtask_a, subtask_b, subtask_c, subtask_d, subtask_e


@pytest.fixture(name="_action_items")
def fixture_action_items(_subtasks, _users, _evidence, graphql_organization):
    _, user_2 = _users
    action_item_1 = create_action_item(
        name="Action item 1",
        description="Action item description 1",
        status="new",
        is_required=True,
        is_recurrent=False,
        metadata={
            'referenceId': 'CF-C-001',
            'organizationId': str(graphql_organization.id),
        },
    )
    action_item_2 = create_action_item(
        name="Action item 2",
        description="Action item description 2",
        status="new",
        is_required=True,
        is_recurrent=False,
        metadata={
            'referenceId': 'CF-C-002',
            'organizationId': str(graphql_organization.id),
        },
    )
    action_item_3 = create_action_item(
        name="Action item 3",
        description="Action item description 3",
        status="completed",
        is_required=True,
        is_recurrent=False,
        due_date=datetime.date.today() + datetime.timedelta(days=1),
        metadata={
            'referenceId': 'CF-C-003',
            'organizationId': str(graphql_organization.id),
        },
    )
    action_item_4 = create_action_item(
        name="Action item 4",
        description="Action item description 4",
        status="new",
        is_required=True,
        is_recurrent=False,
        metadata={
            'referenceId': 'CF-C-004',
            'organizationId': str(graphql_organization.id),
        },
    )

    action_item_2.assignees.add(user_2)
    action_item_2.evidences.add(_evidence)

    return action_item_1, action_item_2, action_item_3, action_item_4


@pytest.fixture(name="_controls")
def fixture_controls(graphql_organization, _evidence, _action_items):
    flag = Flag.objects.filter(
        name='newControlsFeatureFlag', organization=graphql_organization
    )
    if flag:
        flag.delete()

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

    control_2.evidence.add(_evidence)
    control_1.action_items.add(*_action_items)

    return control_1, control_2, control_3, control_4


@pytest.fixture(name="_certifications")
def fixture_certifications(graphql_organization):
    certification_1 = Certification.objects.create(name='SOC 1 type 2')
    certification_2 = Certification.objects.create(name='SOC 2 type 1')
    return certification_1, certification_2


@pytest.fixture(name="_unlocked_org_certifications")
def fixture_unlocked_org_certification(graphql_organization, _certifications):
    certification_1, certification_2 = _certifications
    unlocked_org_cert_1 = UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=certification_1
    )
    unlocked_org_cert_2 = UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=certification_2
    )
    return unlocked_org_cert_1, unlocked_org_cert_2


@pytest.fixture(name="_audit")
def fixture_audit(graphql_organization, graphql_audit_firm, _certifications):
    certification_1, _ = _certifications
    audit_type = 'SOC 2 Type 1'
    Coupon.objects.create(
        organization=graphql_organization,
        type=f'{audit_type} {graphql_audit_firm.name}',
        coupons=1,
    )

    audit_framework_type = AuditFrameworkType.objects.create(
        certification=certification_1,
        audit_type=get_framework_key_from_value(audit_type),
        description=f'{audit_type}',
    )

    return Audit.objects.create(
        organization=graphql_organization,
        audit_type=audit_type,
        audit_firm=graphql_audit_firm,
        audit_framework_type=audit_framework_type,
        completed_at=datetime.datetime.now(pytz.utc),
    )


@pytest.mark.django_db()
def test_migration_organization_to_my_compliance(
    graphql_organization,
    graphql_user,
    _subtasks,
    _action_items,
    _users,
    _controls,
    _unlocked_org_certifications,
    _audit,
):
    _, _, _, subtask_d, _ = _subtasks
    migration = MyComplianceMigration.objects.create(
        organization=graphql_organization,
        created_at=datetime.datetime.now,
        created_by=graphql_user,
        frameworks_detail=', '.join(TESTING_FRAMEWORKS),
        status='i',
    )

    for cert_name in TESTING_FRAMEWORKS:
        Certification.objects.create(name=cert_name)

    migrate_organization(
        graphql_organization,
        migration,
        graphql_user,
        {'frameworks': TESTING_FRAMEWORKS, 'assignee': graphql_user.email},
    )

    assert_archive_old_certifications(graphql_organization)
    assert_unlock_frameworks(graphql_organization, TESTING_FRAMEWORKS)
    assert_action_items(_subtasks, _audit.completed_at)
    assert_feature_flags(graphql_organization)
    assert_controls_deletion(graphql_organization)
    assert_link_ai_to_subtask()
    assert_implement_controls_and_complete_action_items(
        graphql_organization, _audit.completed_at
    )

    migration = MyComplianceMigration.objects.get(organization=graphql_organization)

    assert migration.mapped_subtasks == '3/5'
    assert (
        migration.status_detail
        == 'Control XX-05 migrated successfully\n'
        'Control XX-06 migrated successfully\n'
        'Error seeding the profile SOC 1: '
        '\'SOC 1\'\n'
        'Error seeding the profile '
        'SOC 2 Security: '
        'SeedProfile matching query '
        'does not exist.\n'
        f'Subtask with id {subtask_d.id} and migration_id 0 '
        'not found in mapping file\n'
        'Action Item does not exist: CF-C-100'
    )


def assert_unlock_frameworks(organization: Organization, frameworks: List[str]):
    unlocked_amount = UnlockedOrganizationCertification.objects.filter(
        certification__in=Certification.objects.filter(name__in=frameworks),
        organization=organization,
    ).count()

    assert len(frameworks) == unlocked_amount

    for cert in frameworks:
        assert UnlockedOrganizationCertification.objects.get(
            certification=Certification.objects.get(name=cert),
            organization=organization,
        )


def assert_archive_old_certifications(organization: Organization):
    archived_unlocked_org_cert = (
        ArchivedUnlockedOrganizationCertification.objects.filter(
            organization=organization
        )
    )

    archived_certification_name_1 = (
        archived_unlocked_org_cert.first().certification.name
    )
    archived_certification_name_2 = archived_unlocked_org_cert.last().certification.name

    assert not UnlockedOrganizationCertification.objects.filter(
        certification__name=archived_certification_name_1
    )
    assert not UnlockedOrganizationCertification.objects.filter(
        certification__name=archived_certification_name_2
    )
    assert archived_unlocked_org_cert.count() == 2


def assert_action_items(subtasks, audit_completion_date):
    subtask_a, subtask_b, subtask_c, subtask_d, subtask_e = subtasks
    action_item_1 = ActionItem.objects.get(metadata__referenceId='CF-C-001')
    action_item_2 = ActionItem.objects.get(metadata__referenceId='CF-C-002')
    action_item_3 = ActionItem.objects.get(metadata__referenceId='CF-C-003')

    # this assert group check all values from subtask_a are
    # passed to action_item_1
    assert action_item_1.assignees.first().email == subtask_a.assignee.email
    assert action_item_1.due_date.date() == subtask_a.due_date
    assert action_item_1.evidences.first().name == subtask_a.evidence.first().name
    assert action_item_1.metadata[MetadataFields.REQUIRED_EVIDENCE.value] == 'Yes'
    assert action_item_1.completion_date.date() == subtask_a.completed_on

    # action_item_2 already has an evidence and it has a
    # different assignee from subtask_b, so this assertion
    # group checks that:
    # - values from evidence are passed except
    # for user_2 that should remain in action_item_2 and that
    # - evidence is not repeated
    # - action_item_2 completion date is same as audit completion date
    assert action_item_2.assignees.first().email != subtask_b.assignee.email
    assert action_item_2.due_date.date() == subtask_b.due_date
    assert action_item_2.evidences.count() == 1
    assert action_item_2.evidences.first().name == subtask_b.evidence.first().name
    assert action_item_2.metadata[MetadataFields.REQUIRED_EVIDENCE.value] == 'Yes'
    assert action_item_2.completion_date == audit_completion_date

    # this assert group check values from subtask_c are passed
    # to action_item_3 except for status which is already completed
    # on action_item_3 and that due_date for action_item_3 which is
    # tomorrow is not being change to today.
    assert action_item_3.assignees.first().email == subtask_c.assignee.email
    assert action_item_3.due_date.date() != subtask_c.due_date
    assert action_item_3.evidences.first().name == subtask_c.evidence.first().name
    assert action_item_3.metadata[MetadataFields.REQUIRED_EVIDENCE.value] == 'Yes'


def assert_feature_flags(graphql_organization):
    read_only_playbooks_flag_query = graphql_organization.feature_flags.filter(
        name=read_only_playbooks_feature_flag
    )
    new_controls_flag_query = graphql_organization.feature_flags.filter(
        name=new_controls_feature_flag
    )
    playbooks_flag_query = graphql_organization.feature_flags.filter(
        name=playbooks_feature_flag
    )

    # This asserts checks that new_control flag don't be created twice
    # and stays True
    assert read_only_playbooks_flag_query.count() == 1
    assert read_only_playbooks_flag_query.first().is_enabled is True

    # This asserts checks that roadmap flag don't be created twice
    # and is changed to True
    assert new_controls_flag_query.count() == 1
    assert new_controls_flag_query.first().is_enabled is True

    # This assert checks that readOnlyPlaybooks flag is created and set True
    assert read_only_playbooks_flag_query.count() == 1
    assert read_only_playbooks_flag_query.first().is_enabled is True

    # This assert checks that playbooks flag was deleted
    assert playbooks_flag_query.exists() is False


def assert_controls_deletion(organization):
    assert Control.objects.get(reference_id='XX-05')
    assert Control.objects.get(reference_id='XX-06')
    assert Control.objects.filter(organization=organization).count() == 3
    assert not Control.objects.filter(name='Control test 3').exists()


def assert_link_ai_to_subtask():
    subtask_a = SubTask.objects.get(text='Text subtask a')
    subtask_b = SubTask.objects.get(text='Text subtask b')
    subtask_c = SubTask.objects.get(text='Text subtask c')
    subtask_d = SubTask.objects.get(text='Text subtask that does not match')

    action_item_1 = ActionItem.objects.get(name='Action item 1')
    action_item_2 = ActionItem.objects.get(name='Action item 2')
    action_item_3 = ActionItem.objects.get(name='Action item 3')
    action_item_4 = ActionItem.objects.get(name='Action item 4')

    # These asserts checks that each action_item is linked to
    # corresponding subtask except for subtask_d which is not
    # found on the file.
    assert subtask_a.action_item == action_item_1
    assert subtask_b.action_item == action_item_2
    assert subtask_c.action_item == action_item_3
    assert subtask_d.action_item != action_item_4


def assert_implement_controls_and_complete_action_items(
    organization, audit_completion_date
):
    controls = Control.objects.filter(organization=organization)
    implemented_controls = controls.filter(status=STATUS['IMPLEMENTED'])
    required_action_items = ActionItem.objects.filter(
        is_required=True, controls__in=controls
    )
    completed_required_action_items = required_action_items.filter(status=COMPLETED)

    assert controls.count() == implemented_controls.count()
    assert required_action_items.count() == completed_required_action_items.count()
    for control in controls:
        assert control.implementation_date == audit_completion_date


@pytest.mark.django_db()
def test_apply_seeders(graphql_organization, graphql_user):
    path = (
        f'{os.path.dirname(__file__)}/resources'
        '/[MIGRATION][Playbooks → My Compliance] SOC-S.zip'
    )
    seed_file = File(open(path, 'rb'))
    control_groups = 7
    controls = 61
    controls_action_items = 405
    control_action_items = 7
    certifications = 1

    SeedProfile.objects.create(
        name='[MIGRATION][Playbooks → My Compliance] SOC-S',
        content_description='My Compliance SOC 1 Controls and Action Items.',
        file=seed_file,
    )

    apply_seeders(TESTING_FRAMEWORKS, graphql_organization, graphql_user)

    assert graphql_organization.roadmap
    assert graphql_organization.roadmap.get().groups.count() == control_groups
    assert graphql_organization.controls.count() == controls
    assert (
        ActionItem.objects.filter(
            controls__in=graphql_organization.controls.all()
        ).count()
        == controls_action_items
    )

    control_ac_01 = graphql_organization.controls.get(reference_id='AC-01-SOC')
    assert control_ac_01
    assert control_ac_01.action_items.count() == control_action_items

    assert (
        control_ac_01.certification_sections.filter(
            certification__name='SOC 1',
        ).count()
        == certifications
    )


@pytest.mark.django_db()
def test_archived_unlocked_certifications_are_created(
    graphql_organization, _unlocked_org_certifications
):
    (
        unlocked_org_certification_1,
        unlocked_org_certification_2,
    ) = _unlocked_org_certifications

    unlocked_org_cert_1_id = unlocked_org_certification_1.certification.id
    unlocked_org_cert_2_id = unlocked_org_certification_2.certification.id

    archive_old_certifications(graphql_organization)

    archived_unlocked_org_certifications = (
        ArchivedUnlockedOrganizationCertification.objects.all()
    )

    archived_unlocked_org_cert_1 = archived_unlocked_org_certifications.filter(
        certification_id=unlocked_org_cert_1_id, organization=graphql_organization
    )
    archived_unlocked_org_cert_2 = archived_unlocked_org_certifications.filter(
        certification_id=unlocked_org_cert_2_id, organization=graphql_organization
    )
    assert (
        archived_unlocked_org_cert_1.first().certification.id == unlocked_org_cert_1_id
    )
    assert archived_unlocked_org_cert_1.count() == 1

    assert (
        archived_unlocked_org_cert_2.first().certification.id == unlocked_org_cert_2_id
    )
    assert archived_unlocked_org_cert_2.count() == 1


@pytest.mark.django_db()
def test_old_unlocked_certifications_are_deleted(
    graphql_organization, _unlocked_org_certifications
):
    archive_old_certifications(graphql_organization)

    assert UnlockedOrganizationCertification.objects.count() == 0


@pytest.mark.django_db()
def test_unlock_frameworks(graphql_organization):
    soc_1 = 'SOC 1'
    Certification.objects.create(name=soc_1)
    unlock_frameworks(graphql_organization, [soc_1])

    assert UnlockedOrganizationCertification.objects.filter(
        organization=graphql_organization,
        certification__name=soc_1,
    ).exists()


@pytest.mark.functional(permissions=['control.can_migrate_to_my_compliance'])
def test_migration_mutation(graphql_client, graphql_organization):
    response = graphql_client.execute(
        MIGRATE_ORGANIZATION_TO_MY_COMPLIANCE,
        variables={
            'payload': {
                'id': graphql_organization.id,
                'frameworks': TESTING_FRAMEWORKS,
                'assignee': 'user@heylaika.com',
            }
        },
    )

    assert response['data']['migrateOrganizationToMyCompliance']['success']


@pytest.mark.functional(permissions=['control.can_migrate_to_my_compliance'])
def test_migration_history(graphql_client, graphql_organization, graphql_user):
    migration = MyComplianceMigration.objects.create(
        organization=graphql_organization,
        created_at=datetime.datetime.now,
        created_by=graphql_user,
        frameworks_detail='SOC 1, SOC 2',
        status='d',
    )

    response = graphql_client.execute(
        GET_MIGRATION_HISTORY, variables={'id': str(graphql_organization.id)}
    )

    assert response['data']['migrationHistory']
    assert len(response['data']['migrationHistory']) == 1

    migration_history = response['data']['migrationHistory'][0]
    assert migration_history['frameworksDetail'] == migration.frameworks_detail
