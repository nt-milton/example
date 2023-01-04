import datetime
import io

import pytest
from django.core.files import File

from audit.constants import (
    LEAD_AUDITOR_KEY,
    SECTION_1,
    SECTION_2,
    SECTION_3,
    SECTION_4,
    SECTION_5,
    SOC_2_TYPE_1,
    SOC_2_TYPE_2,
)
from audit.models import AuditAuditor, AuditFeedback, AuditFrameworkType, AuditStatus
from audit.tests.factory import (
    create_audit,
    create_audit_status,
    create_coupon,
    create_soc2_type2_audit,
    get_framework_key_from_value,
    get_framework_type_from_key,
)
from certification.models import Certification
from population.models import AuditPopulation, PopulationData
from user.constants import AUDITOR, AUDITOR_ADMIN, ROLE_ADMIN, ROLE_SUPER_ADMIN
from user.models import User
from user.tests import create_user, create_user_auditor

SECTION_1_CONTENT = 'This is content <div id="cover-delimitator"></div> for the file'
SECTION_CONTENT = 'This is content for the file'
FILE_NAME = 'file_test.html'


@pytest.fixture
def audit(graphql_organization, graphql_audit_firm):
    return create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=graphql_audit_firm,
    )


@pytest.fixture
def audit_soc2_type2(graphql_organization, graphql_audit_firm):
    graphql_organization.system_name = 'Test Org'
    audit = create_audit(
        organization=graphql_organization,
        name='Laika Dev SOC 2 Type 2 Audit 2022',
        audit_firm=graphql_audit_firm,
        audit_type=SOC_2_TYPE_2,
    )
    audit.audit_configuration = {
        "as_of_date": '2022-08-18,2022-08-20',
        "trust_services_categories": ['Security', 'Availability', 'Process Integrity'],
    }
    audit.save()
    AuditStatus.objects.create(audit=audit)
    return audit


@pytest.fixture
def audit_soc2_type1(graphql_organization, graphql_audit_firm):
    audit = create_audit(
        organization=graphql_organization,
        name='Laika Dev SOC 2 Type 1 Audit 2022',
        audit_firm=graphql_audit_firm,
        audit_type=SOC_2_TYPE_1,
    )
    audit.audit_configuration = {
        "as_of_date": "2022-08-20",
        "trust_services_categories": [
            "Confidentiality",
            "Availability",
            "Process Integrity",
        ],
    }
    audit.save()
    return audit


@pytest.fixture
def audit_soc2_type2_with_section(audit_soc2_type2):
    audit_soc2_type2.add_section_files(
        sections=[
            dict(
                name='Section I: This is a test',
                section=SECTION_1,
                file=File(
                    file=io.BytesIO(SECTION_1_CONTENT.encode()),
                    name=FILE_NAME,
                ),
            ),
            dict(
                name='Section II: This is a test section 2',
                section=SECTION_2,
                file=File(
                    file=io.BytesIO(SECTION_CONTENT.encode()),
                    name=FILE_NAME,
                ),
            ),
            dict(
                name='Section III: This is a test section 3',
                section=SECTION_3,
                file=File(
                    file=io.BytesIO(SECTION_CONTENT.encode()),
                    name=FILE_NAME,
                ),
            ),
            dict(
                name='Section IV: This is a test section 4',
                section=SECTION_4,
                file=File(
                    file=io.BytesIO(SECTION_CONTENT.encode()),
                    name=FILE_NAME,
                ),
            ),
            dict(
                name='Section V: This is a test section 5',
                section=SECTION_5,
                file=File(
                    file=io.BytesIO(SECTION_CONTENT.encode()),
                    name=FILE_NAME,
                ),
            ),
        ]
    )
    return audit_soc2_type2


@pytest.fixture
def soc2_type2_coupon(graphql_organization, graphql_audit_firm):
    framework_type = get_framework_type_from_key('SOC_2_TYPE_2')
    return create_coupon(
        graphql_organization,
        coupon_type=f'{framework_type} {graphql_audit_firm.name}',
        coupon_count=10,
    )


@pytest.fixture
def requested_audit_soc2_type2(
    graphql_organization, graphql_audit_firm, graphql_audit_user, soc2_type2_coupon
):
    audit = create_soc2_type2_audit(
        graphql_organization, graphql_audit_firm, graphql_audit_user
    )
    AuditStatus.objects.create(audit=audit, initiated=True, requested=True)
    return audit


@pytest.fixture
def fieldwork_audit_soc2_type2(
    graphql_organization, graphql_audit_firm, graphql_audit_user, soc2_type2_coupon
):
    audit = create_soc2_type2_audit(
        graphql_organization, graphql_audit_firm, graphql_audit_user
    )
    AuditStatus.objects.create(
        audit=audit, initiated=True, requested=True, fieldwork=True
    )

    return audit


@pytest.fixture
def in_draft_report_audit_soc2_type2(
    graphql_organization, graphql_audit_firm, graphql_audit_user, soc2_type2_coupon
):
    audit = create_soc2_type2_audit(
        graphql_organization, graphql_audit_firm, graphql_audit_user
    )
    AuditStatus.objects.create(
        audit=audit,
        initiated=True,
        requested=True,
        fieldwork=True,
        in_draft_report=True,
    )

    return audit


@pytest.fixture
def completed_audit_soc2_type2(
    graphql_organization, graphql_audit_firm, graphql_audit_user, soc2_type2_coupon
):
    audit = create_soc2_type2_audit(
        graphql_organization, graphql_audit_firm, graphql_audit_user
    )
    AuditStatus.objects.create(
        audit=audit,
        initiated=True,
        requested=True,
        fieldwork=True,
        in_draft_report=True,
        completed=True,
    )

    return audit


@pytest.fixture
def audit_population(audit_soc2_type2) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit_soc2_type2,
        name='Name test',
        instructions='Instructions test',
        description='description test',
        display_id='POP-1',
    )

    return population


@pytest.fixture
def laika_admin_user(graphql_organization):
    return create_user(
        graphql_organization,
        email='laika_admin_user@heylaika.com',
        role=ROLE_ADMIN,
        first_name='LW Admin User',
        last_name='Test',
    )


@pytest.fixture
def laika_super_admin(graphql_organization):
    return create_user(
        graphql_organization,
        email='laika_super_admin@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='LW Super Admin User',
    )


@pytest.fixture
def audit_status(audit, laika_super_admin):
    link = 'www.laika.com'
    args = {
        'requested': True,
        'confirm_audit_details': True,
        'engagement_letter_link': link,
        'control_design_assessment_link': link,
        'kickoff_meeting_link': link,
        'initiated': False,
        'initiated_created_at': None,
        'confirm_engagement_letter_signed': True,
        'confirm_control_design_assessment': True,
        'confirm_kickoff_meeting': True,
        'kickoff_call_date': '2022-05-01',
        'fieldwork': False,
        'fieldwork_created_at': None,
        'complete_fieldwork': True,
        'draft_report_generated': True,
        'draft_report': 'draft-report-file.pdf',
        'representation_letter_link': link,
        'management_assertion_link': link,
        'subsequent_events_questionnaire_link': link,
        'in_draft_report': False,
        'in_draft_report_created_at': None,
        'confirm_completion_of_signed_documents': True,
        'final_report': 'final-report.pdf',
        'draft_report_approved': True,
        'draft_report_approved_by': laika_super_admin,
    }
    return create_audit_status(audit=audit, **args)


@pytest.fixture
def auditor_with_firm(graphql_audit_firm):
    return create_user_auditor(
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
        email='matt@heylaika.com',
        role=AUDITOR_ADMIN,
        first_name='Matt',
        last_name='Test',
        user_preferences={"profile": {"alerts": "Never", "emails": "Daily"}},
    )


@pytest.fixture
def auditor_user(graphql_audit_firm):
    return create_user_auditor(
        email='johndoe@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )


@pytest.fixture
def audit_auditor(auditor_user, audit):
    return AuditAuditor.objects.create(
        auditor=auditor_user, audit=audit, title_role=LEAD_AUDITOR_KEY
    )


@pytest.fixture
def auditor_admin_user(graphql_audit_firm):
    return create_user_auditor(
        email='auditoradmin@heylaika.com',
        role=AUDITOR_ADMIN,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )


@pytest.fixture
def population_data(audit_population):
    return PopulationData.objects.create(population=audit_population, data={})


@pytest.fixture
def laika_source_user(graphql_organization):
    return create_user(
        email='laika_source_user@heylaika.com',
        organization=graphql_organization,
        role=ROLE_ADMIN,
        first_name='Name test',
        start_date=datetime.datetime.now(),
        title='title test',
        employment_type='test',
    )


@pytest.fixture
def laika_source_user_terminated(graphql_organization):
    return create_user(
        email='laika_source_user+terminated@heylaika.com',
        organization=graphql_organization,
        role=ROLE_ADMIN,
        first_name='Test user',
        last_name='Terminated',
        start_date=datetime.datetime.now(),
        end_date=datetime.datetime.now(),
        title='title test',
        employment_type='test',
    )


@pytest.fixture
def laika_source_user_invalid_data(graphql_organization):
    return create_user(
        email='laika_source@heylaika.com',
        organization=graphql_organization,
        role=ROLE_ADMIN,
        first_name='    ',
        start_date=datetime.datetime.now(),
        title='',
        employment_type='test',
    )


@pytest.fixture
def graphql_user_valid_data(graphql_user) -> User:
    graphql_user.title = 'test'
    graphql_user.first_name = 'Test name'
    graphql_user.start_date = datetime.datetime.now()
    graphql_user.save()
    return graphql_user


@pytest.fixture
def audit_framework_soc_2_type_1():
    audit_type = 'SOC 2 Type 1'
    certification = Certification.objects.create(name=audit_type)

    framework_type = AuditFrameworkType.objects.create(
        certification=certification,
        audit_type=get_framework_key_from_value(audit_type),
        description=f'{audit_type}',
    )

    return framework_type


@pytest.fixture
def audit_feedback(audit_soc2_type2):
    return AuditFeedback.objects.create(
        audit=audit_soc2_type2,
        rate=3,
        feedback='A dropout will beat a genius through hard work.',
        reason=['Service'],
    )
