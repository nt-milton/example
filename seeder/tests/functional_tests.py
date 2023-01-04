import os
from unittest.mock import patch

import pytest
from django.core.files import File

from action_item.models import ActionItem
from alert.constants import ALERT_TYPES
from alert.models import Alert
from certification.models import Certification, UnlockedOrganizationCertification
from control.models import Control, ControlGroup, RoadMap
from organization.models import OrganizationChecklist
from organization.tests import create_organization
from policy.models import Policy
from program.models import SubTask
from seeder.admin import create_fake_organization
from seeder.constants import ALL_MY_COMPLIANCE_ORGS, DONE, FAILED, IN_PROGRESS
from seeder.models import Seed, SeedAlert, SeedProfile
from seeder.seeders.control_action_items import associate_tags
from seeder.seeders.control_groups import update_group, validate_date_format
from seeder.seeders.controls import add_new_control_when_seeding_multiple
from seeder.tasks import send_alerts, send_seed_email, send_seed_error_email
from tag.models import Tag
from user.constants import CONCIERGE_ROLES
from user.tests import create_user

SOC_2_SECURITY = 'SOC 2 Security'
DICTIONARY = {'tags': 'tag, tag_2, test'}
CONTROL_GROUP_DICT = {
    'reference_id': 'GRP-000',
    'name': 'Updated CG',
    'start_date': '06/30/2022',
    'due_date': '07/31/2022',
    'sort_order': 1,
}

seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.zip'
checklist_seed_file_path = f'{os.path.dirname(__file__)}/resources/checklist_seed.zip'
subtask_seed_file_path = f'{os.path.dirname(__file__)}/resources/subtask.zip'
subtask_no_column_file_path = f'{os.path.dirname(__file__)}/resources/task_seed.zip'
subtask_incomplete_seed_file_path = (
    f'{os.path.dirname(__file__)}/resources/subtask_incomplete.zip'
)
certification_sections_seed_file_path = (
    f'{os.path.dirname(__file__)}/resources/certification_sections.xlsx.zip'
)
controls_seed_file_path = f'{os.path.dirname(__file__)}/resources/controls_seed.zip'
policies_seed_file_path = f'{os.path.dirname(__file__)}/resources/policies.xlsx.zip'
policies_reseed_file_path = (
    f'{os.path.dirname(__file__)}/resources/policies_reseed.xlsx.zip'
)

my_compliance_re_seed = (
    f'{os.path.dirname(__file__)}/resources/re_seed_my_compliance_orgs.zip'
)


@pytest.fixture()
def roadmap(graphql_organization):
    return RoadMap.objects.create(organization=graphql_organization)


@pytest.fixture
def user_test(graphql_organization):
    return create_user(
        graphql_organization,
        email='test-test@heylaika.com',
        role=CONCIERGE_ROLES.get('CONCIERGE'),
        first_name='Test User',
    )


@pytest.fixture
def new_seed(graphql_organization, user_test):
    seed_file = File(open(seed_file_path, "rb"))
    return Seed.objects.create(
        organization=graphql_organization,
        seed_file=File(name='MySeedFile', file=seed_file),
        created_by=user_test,
    )


@pytest.mark.functional(permissions=['user.view_concierge'])
@pytest.mark.skip()
def test_send_seeder_email(graphql_client, graphql_organization, user_test, new_seed):
    seed = Seed.objects.get(id=new_seed.id)
    seed.status = DONE
    send_seed_email(seed)
    assert seed.status == DONE


# This test locks the user column.
@pytest.mark.functional(permissions=['user.view_concierge'])
@pytest.mark.skip()
def test_send_seeder_email_error(
    graphql_client, graphql_organization, user_test, new_seed
):
    seed = Seed.objects.get(id=new_seed.id)
    seed.status = FAILED
    send_seed_error_email(seed)
    assert seed.status == FAILED


@pytest.mark.functional(permissions=['user.view_concierge'])
@pytest.mark.skip()
def test_seed_organization_query(graphql_client, graphql_organization):
    seed_file = File(open(seed_file_path, "rb"))
    profile = SeedProfile.objects.create(
        name='My New Profile Template', file=File(name='MySeedFile', file=seed_file)
    )

    response = graphql_client.execute(
        '''
          query seedOrganization($organizationId: UUID!, $profileId: UUID!) {
            seedOrganization(
                organizationId: $organizationId,
                profileId: $profileId
            ) {
              success
              error {
                code
                message
              }
            }
          }
        ''',
        variables={
            'organizationId': str(graphql_organization.id),
            'profileId': str(profile.id),
        },
    )

    assert response is not None


@pytest.mark.functional(permissions=['user.view_concierge'])
@pytest.mark.skip()
def test_resolve_concierge_alerts(graphql_client, user_test, new_seed):
    alert = Alert.objects.create(
        sender=None, receiver=user_test, type=ALERT_TYPES.get('SEEDING_FINISH_REMINDER')
    )

    seed = Seed.objects.get(id=new_seed.id)

    SeedAlert.objects.create(alert=alert, seed=seed)

    GET_CONCIERGE_ALERTS = '''
        query ConciergeAlerts {
            conciergeAlerts {
                alerts {
                    seed {
                        id
                        organization {
                            id
                        }
                        seedFile
                    }
                }
            }
        }
    '''

    executed = graphql_client.execute(GET_CONCIERGE_ALERTS)

    response = executed['data']['conciergeAlerts']

    assert response['alerts'] is None
    # assert seed is True


def create_seed_from_file(graphql_organization, seed_file, user_test):
    return Seed.objects.create(
        organization=graphql_organization,
        seed_file=File(name='MySeedFile', file=seed_file),
        created_by=user_test,
    ).run(run_async=False, should_send_alerts=False)


@pytest.mark.functional
def test_seed_checklist(graphql_organization, user_test):
    updated_seed = create_seed_from_file(
        graphql_organization, File(open(checklist_seed_file_path, 'rb')), user_test
    )
    checklist = OrganizationChecklist.objects.get(organization=graphql_organization)

    assert updated_seed.status == DONE
    assert 3 == checklist.action_item.steps.filter(metadata__isTemplate=True).count()
    assert 2 == checklist.tags.count()


@pytest.mark.parametrize(
    'path, status, count',
    [
        (checklist_seed_file_path, DONE, 0),
        (subtask_seed_file_path, DONE, 1),
        (subtask_no_column_file_path, FAILED, 0),
        (subtask_incomplete_seed_file_path, FAILED, 0),
    ],
)
@pytest.mark.functional
def test_seed_subtask(graphql_organization, user_test, path, status, count):
    updated_seed = create_seed_from_file(
        graphql_organization, File(open(path, 'rb')), user_test
    )

    assert updated_seed.status == status
    assert SubTask.objects.all().count() == count


@pytest.mark.functional
def test_seed_certification_sections(graphql_organization, user_test):
    updated_seed = execute_seed(
        graphql_organization, certification_sections_seed_file_path, user_test
    )

    [first_cert, second_cert] = Certification.objects.all()
    first_cert_sections = first_cert.sections.all()
    second_cert_sections = second_cert.sections.all()

    TOTAL_CERT_SECTIONS = 2

    assert str(first_cert) == 'Fake Certification 1'
    assert len(first_cert_sections) == TOTAL_CERT_SECTIONS
    assert str(second_cert) == 'Fake Certification 2'
    assert len(second_cert_sections) == TOTAL_CERT_SECTIONS
    assert updated_seed.status == DONE


@pytest.mark.functional
def test_seed_organization_controls(graphql_organization, user_test):
    updated_seed = execute_seed(
        graphql_organization, controls_seed_file_path, user_test
    )

    controls = Control.objects.filter(organization_id=graphql_organization.id)

    assert updated_seed.status == DONE
    assert len(controls) == 55

    action_items = ActionItem.objects.filter(controls__in=controls)
    assert len(action_items) == 153

    lai_001 = action_items.get(metadata__referenceId='LAI-001')
    assert len(lai_001.controls.all()) == 1
    assert lai_001.controls.get(reference_id='TPM-001')

    control_groups = ControlGroup.objects.filter(
        roadmap__organization_id=graphql_organization.id
    )

    assert len(control_groups) == 3
    assert control_groups.get(reference_id='GRP-001')

    grp_001 = control_groups.get(reference_id='GRP-001')
    assert grp_001.controls.get(reference_id='AMG-001')

    control_amg_001 = grp_001.controls.get(reference_id='AMG-001')

    assert len(control_amg_001.action_items.all()) == 6

    sections = control_amg_001.certification_sections.filter(
        certification__name=SOC_2_SECURITY,
    )
    assert len(sections) == 2
    assert control_amg_001.certification_sections.get(name='CC6.1')
    assert control_amg_001.certification_sections.get(name='CC6.5')


@pytest.mark.functional
def test_single_seed_policies(graphql_organization, user_test):
    updated_seed = execute_seed(
        graphql_organization, policies_seed_file_path, user_test
    )

    [first_policy, second_policy] = Policy.objects.all()

    [first_policy_tag_1, first_policy_tag_2] = first_policy.tags.all()
    first_policy_file = first_policy.draft.name.split('/')[-1]

    assert str(first_policy) == 'Data Privacy Policy'
    assert first_policy.control_family is None
    assert first_policy.policy_type == 'Policy'
    assert str(first_policy_tag_1).strip() == 'Data Privacy'
    assert str(first_policy_tag_2).strip() == 'Data Privacy Policy'
    assert first_policy_file == 'Data_Privacy_Policy.docx'

    [second_policy_tag_1, second_policy_tag_2] = second_policy.tags.all()
    second_policy_file = second_policy.draft.name.split('/')[-1]

    assert str(second_policy) == 'Data Privacy Procedure'
    assert second_policy.control_family is None
    assert second_policy.policy_type == 'Procedure'
    assert str(second_policy_tag_1).strip() == 'Data Privacy'
    assert str(second_policy_tag_2).strip() == 'Data Privacy Procedure'
    assert second_policy_file == 'Data_Privacy_Procedure.docx'

    assert updated_seed.status == DONE


@pytest.mark.functional
def test_create_fake_organization_for_seeding():
    fake_org = create_fake_organization()
    assert fake_org.name == ALL_MY_COMPLIANCE_ORGS
    assert fake_org.is_internal is True


@pytest.mark.functional
def test_re_seed_my_compliance_orgs(graphql_user):
    my_test_org = create_organization(name='My Test Org')

    Control.objects.create(
        organization=my_test_org, reference_id='AC-05', name='Test Control'
    )
    soc2_certification = Certification.objects.create(name=SOC_2_SECURITY)
    UnlockedOrganizationCertification.objects.create(
        organization=my_test_org, certification=soc2_certification
    )

    Seed.objects.create(
        organization=create_fake_organization(),
        status=IN_PROGRESS,
        seed_file=File(name='seed', file=File(open(my_compliance_re_seed, 'rb'))),
        content_description='Re-seed orgs 🔥',
        created_by=graphql_user,
    ).run(run_async=False).create_and_run_upsert_seeds()

    assert Control.objects.filter(organization=my_test_org).count() == 2
    assert (
        Control.objects.get(organization=my_test_org, reference_id='AC-05').name
        == '[LOE EDITION] Separation of Duties'
    )

    # 4 seeds include 3 orgs:
    # graphql_organization within graphql_user fixture
    # fake_org
    # My Test Org
    assert Seed.objects.count() == 3
    assert my_test_org.seedfiles.count() == 1


@pytest.mark.django_db()
def test_add_new_control_when_seeding_multiple(graphql_organization):
    Control.objects.create(
        organization=graphql_organization, reference_id='AC-05', name='Test Control'
    )
    soc2_certification = Certification.objects.create(name=SOC_2_SECURITY)
    UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=soc2_certification
    )

    add_new_control_when_seeding_multiple(
        dictionary={
            'name': 'New control',
            'reference_id': 'AC-06',
            'description': 'My description',
            SOC_2_SECURITY: ['y', 'CCO.1'],
        },
        organization=graphql_organization,
        status_detail=[],
    )

    assert Control.objects.get(organization=graphql_organization, reference_id='AC-06')


def execute_seed(organization, path, user_test) -> Seed:
    return Seed.objects.create(
        organization=organization,
        seed_file=File(name='MySeedFile', file=File(open(path, 'rb'))),
        created_by=user_test,
    ).run(run_async=False, should_send_alerts=False)


class MockRequest(object):
    def __init__(self, user=None):
        self.user = user


@pytest.mark.functional
def test_send_alerts_when_done(new_seed):
    new_seed.status = 'd'
    new_seed.save()

    with patch('laika.aws.ses.ses.send_email') as send_email_mck:
        send_alerts(instance=new_seed)
        send_email_mck.assert_called_once()

    assert Alert.objects.filter(
        receiver=new_seed.created_by, type='SEEDING_FINISH_REMINDER'
    ).exists()


@pytest.mark.functional
def test_send_alerts_when_failed(new_seed):
    new_seed.status = 'f'
    new_seed.save()

    with patch('laika.aws.ses.ses.send_email') as send_email_mck:
        send_alerts(instance=new_seed)
        send_email_mck.assert_called_once()

    assert Alert.objects.all().count() == 0


@pytest.mark.functional
def test_associate_tags(graphql_organization, user_test):
    ActionItem.objects.get_or_create(
        name='Test AI',
        defaults={
            'description': 'Test',
            'metadata': {
                'isTemplate': True,
                'category': {'id': '1231232', 'name': 'Name AI'},
            },
        },
    )
    action_item = ActionItem.objects.get(name='Test AI')
    associate_tags(DICTIONARY, graphql_organization, action_item)
    tags = Tag.objects.all()

    assert tags.count() == 3
    assert tags[0].name == 'tag'


@pytest.mark.functional
def test_update_control_group(roadmap):
    new_group = ControlGroup.objects.create(
        roadmap=roadmap, reference_id='GRP-000', name='Default name', sort_order=0
    )

    update_group(False, CONTROL_GROUP_DICT, new_group, True)
    groups = ControlGroup.objects.all()

    assert groups[0].name == 'Updated CG'
    assert groups[0].sort_order == 1


@pytest.mark.functional
def test_validate_date_format():
    test_1 = validate_date_format('07-089-0882-sdaas')
    test_2 = validate_date_format('07/31/2022')
    test_3 = validate_date_format('03-12-2021')

    assert test_1 is False
    assert str(test_2) == '2022-07-31 00:00:00'
    assert str(test_3) == '2021-03-12 00:00:00'
