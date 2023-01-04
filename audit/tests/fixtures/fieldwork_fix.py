import os
import tempfile

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files import File

from audit.constants import LAIKA_SOURCE_POPULATION_AND_SAMPLES_FEATURE_FLAG
from audit.models import Audit
from auditee.tests.pop_completeness_tests import template_seed_file_path
from auditee.tests.test_utils import create_evidence_attachment
from comment.constants import RESOLVED
from comment.models import Comment, Reply
from drive.models import DriveEvidence, DriveEvidenceData
from evidence.constants import LAIKA_PAPER
from feature.models import Flag
from fieldwork.constants import (
    DOCUMENT_FETCH_TYPE,
    ER_TYPE,
    LAIKA_EVIDENCE_SOURCE_TYPE,
    MONITOR_SOURCE_TYPE,
    OBJECT_SOURCE_TYPE,
    OFFICER_FETCH_TYPE,
    OTHER_SOURCE_TYPE,
    POLICY_FETCH_TYPE,
    POLICY_SOURCE_TYPE,
    REQ_STATUS_DICT,
    TRAINING_FETCH_TYPE,
)
from fieldwork.models import (
    Attachment,
    AttachmentSourceType,
    Criteria,
    CriteriaRequirement,
    Evidence,
    EvidenceMetric,
    FetchLogic,
    Requirement,
    TemporalAttachment,
    Test,
)
from integration.models import PAYROLL, PROJECT_MANAGEMENT
from integration.tests import create_connection_account
from integration.tests.factory import create_integration
from monitor.models import Monitor, MonitorHealthCondition, MonitorInstanceStatus
from monitor.tests.factory import (
    create_monitor,
    create_monitor_result,
    create_organization_monitor,
)
from objects.models import LaikaObject, LaikaObjectType
from policy.tests.factory import create_published_empty_policy
from population.constants import POPULATION_SOURCE_DICT
from population.models import (
    AuditPopulation,
    AuditPopulationEvidence,
    PopulationCompletenessAccuracy,
    PopulationData,
    Sample,
)
from population.utils import set_sample_name
from training.models import Training
from user.models import Officer, Team, TeamMember
from vendor.models import OrganizationVendor
from vendor.tests.factory import create_vendor

ER_OPEN_STATUS = 'open'


@pytest.fixture
def evidence(graphql_organization, audit):
    evidence = Evidence.objects.create(
        audit=audit,
        display_id='1',
        name='Ev1',
        instructions='yyyy',
        status=ER_OPEN_STATUS,
    )
    create_evidence_attachment(graphql_organization, evidence)

    return evidence


@pytest.fixture
def evidence_no_attachments(graphql_organization, audit):
    evidence = Evidence.objects.create(
        audit=audit,
        display_id='1',
        name='Ev1',
        instructions='yyyy',
        status=ER_OPEN_STATUS,
    )
    return evidence


@pytest.fixture
def fetch_logic_object_device(audit):
    return FetchLogic.objects.create(
        code='FL-1',
        type='object_device',
        logic={'query': 'select lo_devices.name from lo_devices;'},
        audit=audit,
        description='Laika Object devices results',
    )


@pytest.fixture
def fetch_logic_officer_log(audit):
    return FetchLogic.objects.create(
        code='FL-2',
        type=OFFICER_FETCH_TYPE,
        description='This is the fetch description',
        logic={'query': 'select officers.title from officers;'},
        audit=audit,
    )


@pytest.fixture
def fetch_logic_document(audit):
    return FetchLogic.objects.create(
        code='FL-3',
        type=DOCUMENT_FETCH_TYPE,
        description='This is the fetch doc description',
        logic={
            'query': (
                "select documents.name from documents where 'bc/dr' ="
                " ANY(documents.tags) OR lower(documents.name) like '%bc/dr%';"
            )
        },
        audit=audit,
    )


@pytest.fixture
def fetch_logic_policy(audit):
    return FetchLogic.objects.create(
        code='FL-6',
        type=POLICY_FETCH_TYPE,
        description='This is the fetch policy description',
        logic={
            'query': (
                "select policies.name from policies where lower(policies.name) like"
                " '%empty-test%'"
            )
        },
        audit=audit,
    )


@pytest.fixture
def fetch_logic_team_log(audit):
    return FetchLogic.objects.create(
        audit=audit,
        code='FL-1',
        type='team_log',
        logic={
            'query': (
                'select teams.name from teams where '
                'lower(teams.name) like \'%test_team%\';'
            )
        },
    )


@pytest.fixture
def fetch_logic_training_log(audit):
    return FetchLogic.objects.create(
        code='FL-4',
        type=TRAINING_FETCH_TYPE,
        logic={'query': 'select trainings.name from trainings;'},
        audit=audit,
    )


@pytest.fixture()
def lo_device(graphql_organization):
    return LaikaObjectType.objects.create(
        organization=graphql_organization,
        display_name='object_device',
        display_index=1,
        type_name='device',
    )


@pytest.fixture()
def lo_account(graphql_organization):
    return LaikaObjectType.objects.create(
        organization=graphql_organization,
        display_name='object_account',
        display_index=2,
        type_name='account',
    )


@pytest.fixture
def requirement(audit):
    test_requirement = Requirement.objects.create(
        audit=audit,
        display_id='LCL-1',
        name='LCL-1',
    )
    return test_requirement


@pytest.fixture
def completed_requirement(audit):
    requirement = Requirement.objects.create(
        audit=audit,
        display_id='LCL-10',
        name='LCL-10',
        status=REQ_STATUS_DICT['Completed'],
    )
    return requirement


@pytest.fixture
def under_review_requirement(audit):
    requirement = Requirement.objects.create(
        audit=audit,
        display_id='LCL-20',
        name='LCL-20',
        status=REQ_STATUS_DICT['Under Review'],
    )
    return requirement


@pytest.fixture
def exceptions_noted_test(requirement):
    return Test.objects.create(
        display_id='Test-1',
        name='Test #1',
        requirement=requirement,
        result='exceptions_noted',
    )


@pytest.fixture
def no_exceptions_noted_test(requirement):
    return Test.objects.create(
        display_id='Test-2',
        name='Test #2',
        requirement=requirement,
        result='no_exceptions_noted',
    )


@pytest.fixture
def not_tested_test(requirement):
    return Test.objects.create(
        display_id='Test-3',
        name='Test #3',
        requirement=requirement,
        result='not_tested',
    )


@pytest.fixture
def criteria():
    return Criteria.objects.create(
        display_id='CC 1.1',
    )


@pytest.fixture
def criteria_requirement(criteria, requirement):
    return CriteriaRequirement.objects.create(
        criteria=criteria, requirement=requirement
    )


@pytest.fixture
def requirement_with_test(
    requirement, exceptions_noted_test, no_exceptions_noted_test, not_tested_test
):
    return requirement


@pytest.fixture
def evidence_attachment(evidence):
    return Attachment.objects.create(name='Evidence Attachment', evidence=evidence)


POP_INSTRUCTIONS = 'Instructions test'
POP_DESC = 'description test'


@pytest.fixture
def audit_population(audit_soc2_type2):
    population = AuditPopulation.objects.create(
        audit=audit_soc2_type2,
        name='Name test',
        display_id='POP-1',
        instructions=POP_INSTRUCTIONS,
        description=POP_DESC,
        selected_source=POPULATION_SOURCE_DICT['manual'],
        configuration_seed=[
            {
                "type": "MULTISELECT",
                "question": "Configuration question test",
                "answer_column": ["DEMO", "TEST", "NAME"],
            }
        ],
    )

    return population


@pytest.fixture
def audit_population_people_source_pop_2(audit_soc2_type2):
    population = AuditPopulation.objects.create(
        audit=audit_soc2_type2,
        default_source='People',
        name='POP-2',
        display_id='POP-2',
        instructions=POP_INSTRUCTIONS,
        description=POP_DESC,
        selected_source='laika_source',
        configuration_seed=[
            {
                "type": "MULTISELECT",
                "question": "Configuration question test",
                "answer_column": ["DEMO", "TEST", "NAME"],
            }
        ],
    )

    return population


@pytest.fixture
def sample_evidence(audit_soc2_type2) -> Evidence:
    evidence = Evidence.objects.create(
        audit=audit_soc2_type2,
        display_id='1',
        name='Ev1',
        instructions='yyyy',
        er_type=dict(ER_TYPE)['sample_er'],
    )

    return evidence


@pytest.fixture
def sample_evidence_2(audit_soc2_type2) -> Evidence:
    evidence = Evidence.objects.create(
        audit=audit_soc2_type2,
        display_id='2',
        name='Ev2',
        instructions='yyyy',
        er_type=dict(ER_TYPE)['sample_er'],
    )

    return evidence


@pytest.fixture
def sample():
    return Sample.objects.create()


COMMENT_CONTENT = 'Comment content'
REPLY_CONTENT = 'This is a reply'


@pytest.fixture
def jarvis_comment(graphql_audit_user):
    return Comment.objects.create(owner=graphql_audit_user, content=COMMENT_CONTENT)


@pytest.fixture
def jarvis_resolved_comment(graphql_audit_user):
    return Comment.objects.create(
        owner=graphql_audit_user, content=COMMENT_CONTENT, state=RESOLVED
    )


@pytest.fixture
def jarvis_reply(graphql_audit_user, jarvis_comment):
    return Reply.objects.create(
        owner=graphql_audit_user, content=REPLY_CONTENT, parent=jarvis_comment
    )


@pytest.fixture
def healthy_exception_monitor():
    return create_monitor(
        id='101',
        name='Exception monitor healthy test',
        query='select name from healthy monitor',
        status=MonitorInstanceStatus.HEALTHY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )


@pytest.fixture
def healthy_evidence_monitor():
    return create_monitor(
        id='102',
        name='Evidence monitor healthy test',
        query='select name from healthy monitor',
        status=MonitorInstanceStatus.HEALTHY,
    )


@pytest.fixture
def flagged_monitor():
    return create_monitor(
        id='100',
        name='Monitor test flagged',
        query='select name from flagged monitor',
        status=MonitorInstanceStatus.TRIGGERED,
    )


@pytest.fixture
def organization_monitor(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(name='Monitor Test', query='select name from test'),
    )


@pytest.fixture
def organization_monitor2(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(name='Monitor Test2', query='select name from test2'),
    )


@pytest.fixture
def organization_monitor_flagged(graphql_organization, flagged_monitor):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=flagged_monitor,
        status=MonitorInstanceStatus.TRIGGERED,
    )


@pytest.fixture
def monitor_result1(organization_monitor):
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )


@pytest.fixture
def monitor_result2(organization_monitor2):
    create_monitor_result(
        organization_monitor=organization_monitor2,
        result={'columns': ['id'], 'data': ['123']},
    )


@pytest.fixture
def monitor_result_flagged(organization_monitor_flagged):
    create_monitor_result(
        organization_monitor=organization_monitor_flagged,
        result={'columns': ['id'], 'data': ['123']},
        status=MonitorInstanceStatus.TRIGGERED,
    )


@pytest.fixture
def er_metrics(evidence):
    return EvidenceMetric.objects.create(
        evidence_request=evidence,
        monitors_count=2,
        integrations_counter={PROJECT_MANAGEMENT: 1, 'general': 2, PAYROLL: 1},
    )


@pytest.fixture
def finch_integration():
    return create_integration(
        vendor_name='BambooHR',
        metadata={
            'finchProvider': 'bamboo_hr',
        },
        category=PAYROLL,
    )


@pytest.fixture
def finch_connection_account(finch_integration, graphql_user, graphql_organization):
    return create_connection_account(
        'Finch',
        integration=finch_integration,
        created_by=graphql_user,
        organization=graphql_organization,
    )


@pytest.fixture
def github_integration():
    return create_integration(vendor_name='Github', category=PROJECT_MANAGEMENT)


@pytest.fixture
def github_connection_account(github_integration, graphql_user, graphql_organization):
    return create_connection_account(
        'Github',
        integration=github_integration,
        created_by=graphql_user,
        organization=graphql_organization,
    )


TEST_EMAIL = 'laika@laika.com'
TEST_ORG = 'Organization Test'


@pytest.fixture
def lo_for_device_type(lo_device, finch_connection_account):
    laika_object = {
        'object_type': lo_device,
        'is_manually_created': False,
        'data': dict(first_name='Laika', last_name=TEST_ORG, email=TEST_EMAIL),
        'connection_account': finch_connection_account,
    }
    return LaikaObject.objects.create(**laika_object)


@pytest.fixture
def lo_for_account_type(lo_account, github_connection_account):
    laika_object = {
        'object_type': lo_account,
        'is_manually_created': False,
        'data': dict(first_name='Laika', last_name=TEST_ORG, email=TEST_EMAIL),
        'connection_account': github_connection_account,
    }
    return LaikaObject.objects.create(**laika_object)


@pytest.fixture
def lo_for_device_type_manual(lo_device, finch_connection_account):
    laika_object = {
        'object_type': lo_device,
        'is_manually_created': True,
        'data': dict(first_name='LaikaManual', last_name=TEST_ORG, email=TEST_EMAIL),
    }
    return LaikaObject.objects.create(**laika_object)


@pytest.fixture
def training(graphql_organization):
    return Training.objects.create(
        organization=graphql_organization,
        name='A very important training',
        roles=['OrganizationAdmin'],
        category=['Some category'],
        description='A description',
        slides='',
    )


@pytest.fixture
def tmp_attachment_document_type(audit, document):
    return TemporalAttachment.objects.create(
        file=File(file=tempfile.TemporaryFile(), name='test_doc.pdf'),
        document=document.evidence,
        name='test_doc.pdf',
        audit=audit,
    )


@pytest.fixture
def tmp_attachment_policy_type(audit, policy):
    return TemporalAttachment.objects.create(
        file=File(file=tempfile.TemporaryFile(), name='Empty-test'),
        policy=policy,
        name='Empty-test',
        audit=audit,
    )


@pytest.fixture
def tmp_attachment_training_type(audit, training):
    return TemporalAttachment.objects.create(
        file=File(file=tempfile.TemporaryFile(), name='test_training.pdf'),
        training=training,
        name='test_training.pdf',
        audit=audit,
    )


@pytest.fixture
def team(graphql_organization, laika_admin_user):
    team = Team.objects.create(organization=graphql_organization, name='Test_Team')
    TeamMember.objects.create(
        role='Member', phone='123', user=laika_admin_user, team=team
    )
    return team


@pytest.fixture
def tmp_attachment_team_type(audit, team):
    return TemporalAttachment.objects.create(
        file=File(file=tempfile.TemporaryFile(), name='test_team.pdf'),
        team=team,
        name='test_team.pdf',
        audit=audit,
    )


@pytest.fixture
def attachment_source_types(audit, team):
    return AttachmentSourceType.objects.bulk_create(
        [
            AttachmentSourceType(name=OTHER_SOURCE_TYPE),
            AttachmentSourceType(name=OBJECT_SOURCE_TYPE),
            AttachmentSourceType(name=MONITOR_SOURCE_TYPE),
            AttachmentSourceType(name=LAIKA_EVIDENCE_SOURCE_TYPE),
            AttachmentSourceType(name=POLICY_SOURCE_TYPE),
        ],
        ignore_conflicts=True,
    )


@pytest.fixture
def policy(graphql_organization, graphql_user):
    return create_published_empty_policy(
        organization=graphql_organization, user=graphql_user
    )


@pytest.fixture
def document(graphql_organization, graphql_user):
    file = File(file=tempfile.TemporaryFile(), name='Laikapaper File')
    drive_evidence_data = DriveEvidenceData(
        type=LAIKA_PAPER,
        file=file,
    )
    return DriveEvidence.objects.custom_create(
        organization=graphql_organization,
        owner=graphql_user,
        drive_evidence_data=drive_evidence_data,
    )


@pytest.fixture
def vendor(graphql_organization):
    vendor = create_vendor(
        name='New Vendor',
        website='www.new-vendor.com',
        description='This is a new vendor',
        is_public=True,
    )
    OrganizationVendor.objects.create(vendor=vendor, organization=graphql_organization)
    return vendor


@pytest.fixture
def officer(graphql_organization, laika_admin_user):
    return Officer.objects.create(
        organization=graphql_organization, user=laika_admin_user, name='Test_Officer'
    )


@pytest.fixture
def fetch_logic_officer(audit):
    return FetchLogic.objects.create(
        code='FL-1',
        type=OFFICER_FETCH_TYPE,
        logic={'query': 'select officers.name from officers;'},
        audit=audit,
        description='Officers result',
    )


@pytest.fixture
def audit_population_with_samples(
    audit_soc2_type2: Audit,
    audit_population: AuditPopulation,
    audit_population_evidence: AuditPopulationEvidence,
    population_data_sample,
) -> AuditPopulation:
    audit_population_evidence.evidence_request.population_sample.set(
        population_data_sample
    )
    samples = Sample.objects.filter(
        evidence_request=audit_population_evidence.evidence_request
    )
    for sample in samples:
        set_sample_name(sample)
    return audit_population_evidence


@pytest.fixture
def population_data_sample(audit_population):
    name = "Employee Name"
    PopulationData.objects.bulk_create(
        [
            PopulationData(
                data={name: "Joseph"}, population=audit_population, is_sample=True
            ),
            PopulationData(
                data={name: "Jotaro"}, population=audit_population, is_sample=True
            ),
            PopulationData(
                data={name: "Josuke"}, population=audit_population, is_sample=True
            ),
        ]
    )
    return PopulationData.objects.all()


@pytest.fixture
def laika_source_population_data_sample(audit_population_people_source_pop_2):
    name = "Name"
    PopulationData.objects.bulk_create(
        [
            PopulationData(
                data={name: "Joseph"},
                population=audit_population_people_source_pop_2,
                is_sample=True,
            ),
            PopulationData(
                data={name: "Jotaro"},
                population=audit_population_people_source_pop_2,
                is_sample=True,
            ),
            PopulationData(
                data={name: "Josuke"},
                population=audit_population_people_source_pop_2,
                is_sample=True,
            ),
        ]
    )
    return PopulationData.objects.all()


@pytest.fixture
def sample_evidence_with_attachment(
    graphql_organization, audit_population_with_samples
):
    evidence = audit_population_with_samples.evidence_request
    sample = evidence.population_sample.first()
    create_evidence_attachment(graphql_organization, evidence, 'er_attachment')
    create_evidence_attachment(
        graphql_organization, evidence, 'sample_attachment', sample_id=sample.id
    )


@pytest.fixture()
def laika_source_population_and_samples_feature_flag(graphql_organization):
    Flag.objects.get_or_create(
        name=LAIKA_SOURCE_POPULATION_AND_SAMPLES_FEATURE_FLAG,
        organization=graphql_organization,
        is_enabled=True,
    )


@pytest.fixture
def audit_laika_source_population(audit_soc2_type2):
    population = AuditPopulation.objects.create(
        audit=audit_soc2_type2,
        name='Population 2',
        display_id='POP-2',
        instructions=POP_INSTRUCTIONS,
        description=POP_DESC,
        selected_source=POPULATION_SOURCE_DICT['laika_source'],
    )

    return population


@pytest.fixture
def evidence_with_attachments(graphql_organization, audit):
    evidence = Evidence.objects.create(
        audit=audit,
        display_id='2',
        name='Ev2',
        instructions='yyyy',
        status=ER_OPEN_STATUS,
    )
    create_evidence_attachment(graphql_organization, evidence)

    return evidence


@pytest.fixture
def completeness_accuracy(audit_population):
    return PopulationCompletenessAccuracy.objects.create(
        population=audit_population,
        name='template_seed.xlsx',
        file=File(open(template_seed_file_path, "rb")),
    )


@pytest.fixture
def soc2_type2_criteria(audit_soc2_type2: Audit) -> Criteria:
    return Criteria.objects.create(
        display_id='CC1.1',
        audit=audit_soc2_type2,
        description=(
            'The entity demonstrates a commitment to integrity and ethical values.'
        ),
    )


@pytest.fixture
def pop1_population_data(audit_population):
    return PopulationData.objects.create(
        data={'Employee Name': 'John Doe'}, population=audit_population, is_sample=True
    )


@pytest.fixture
def evidence_monitor_file_path():
    return f'{os.path.dirname(__file__)}/resources/evidence_monitor.xlsx'


@pytest.fixture
def exception_monitor_file_path():
    return f'{os.path.dirname(__file__)}/resources/exception_monitor.xlsx'


@pytest.fixture
def not_monitor_file_path():
    return f'{os.path.dirname(__file__)}/resources/not_monitor.txt'


@pytest.fixture
def monitor_attachment_source_type(attachment_source_types):
    source_type = AttachmentSourceType.objects.get(name=MONITOR_SOURCE_TYPE)
    source_type.template = [
        {
            "question": "Test question 1?",
            "source": "answer = origin_source_object.name",
        },
        {
            "question": "Test question 2?",
            "source": "answer = origin_source_object.description",
        },
    ]
    source_type.save()
    return source_type


@pytest.fixture
def evidence_with_monitor_attachments(
    evidence_monitor_file_path: str,
    exception_monitor_file_path: str,
    not_tested_test: Test,
    evidence: Evidence,
    healthy_exception_monitor: Monitor,
    healthy_evidence_monitor: Monitor,
    monitor_attachment_source_type,
):
    content_type = ContentType.objects.get(model='monitor')
    Attachment.objects.create(
        evidence_id=evidence.id,
        file=File(open(evidence_monitor_file_path, "rb")),
        from_fetch=True,
        source_id=monitor_attachment_source_type.id,
        object_id=healthy_evidence_monitor.id,
        content_type_id=content_type.id,
    )
    Attachment.objects.create(
        evidence_id=evidence.id,
        file=File(open(exception_monitor_file_path, "rb")),
        from_fetch=True,
        source_id=monitor_attachment_source_type.id,
        object_id=healthy_exception_monitor.id,
        content_type_id=content_type.id,
    )
    not_tested_test.requirement.evidence.set([evidence])
    return evidence
