import io
from unittest.mock import Mock, patch

import pytest
from django.core.files import File

from audit.constants import SECTION_1, SECTION_2, SECTION_3, SECTION_4, SECTION_5
from audit.models import Audit, AuditStatus, FrameworkReportTemplate
from audit.sections_factory.SOC2_Type2_sections_factory import (
    SOC2Type2Section1,
    SOC2Type2Section2,
    SOC2Type2Section3,
    SOC2Type2SectionsFactory,
)
from fieldwork.models import Criteria, Requirement

TEMPLATE_CONTENT = 'This is content for the template'
FILE_NAME = 'file_test.html'
ORGANIZATION_SYSTEM_NAME = 'Test Org'


@pytest.fixture
def soc2_type2_sections_factory(audit_soc2_type2):
    return SOC2Type2SectionsFactory(audit=audit_soc2_type2)


@pytest.fixture
def soc2_type2_section1(audit_soc2_type2):
    return SOC2Type2Section1(audit=audit_soc2_type2)


@pytest.fixture
def soc2_type2_section2(audit_soc2_type2):
    return SOC2Type2Section2(audit=audit_soc2_type2)


@pytest.fixture
def soc2_type2_section3(audit_soc2_type2):
    return SOC2Type2Section3(audit=audit_soc2_type2)


@pytest.fixture
def soc2_type2_sections_factory_with_templates(audit_soc2_type2):
    audit_soc2_type2.audit_framework_type.templates.add(
        FrameworkReportTemplate(
            name='Section I: This is a test section 1',
            section=SECTION_1,
            file=File(
                file=io.BytesIO(TEMPLATE_CONTENT.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section II: This is a test section 2',
            section=SECTION_2,
            file=File(
                file=io.BytesIO(TEMPLATE_CONTENT.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section III: This is a test section 3',
            section=SECTION_3,
            file=File(
                file=io.BytesIO(TEMPLATE_CONTENT.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section IV: This is a test section 4',
            section=SECTION_4,
            file=File(
                file=io.BytesIO(TEMPLATE_CONTENT.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section V: This is a test section 5',
            section=SECTION_5,
            file=File(
                file=io.BytesIO(TEMPLATE_CONTENT.encode()),
                name=FILE_NAME,
            ),
        ),
        bulk=False,
    )
    return SOC2Type2SectionsFactory(audit=audit_soc2_type2)


@pytest.fixture
def is_qualified_criteria(audit_soc2_type2: Audit) -> Criteria:
    return Criteria.objects.create(
        display_id='CC1.1', audit=audit_soc2_type2, description='yyy', is_qualified=True
    )


@pytest.fixture
def criteria(audit_soc2_type2: Audit) -> Criteria:
    return Criteria.objects.create(
        display_id='CC1.1', audit=audit_soc2_type2, description='yyy'
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_1_without_template(
    get_requirements_by_args_mock,
    get_criteria_by_audit_id_mock: Mock,
    soc2_type2_sections_factory: SOC2Type2SectionsFactory,
):
    assert soc2_type2_sections_factory.create_section_1() is None


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_2_without_template(
    get_criteria_by_audit_id_mock: Mock,
    soc2_type2_sections_factory: SOC2Type2SectionsFactory,
):
    assert soc2_type2_sections_factory.create_section_2() is None


@pytest.mark.functional
def test_create_section_3_without_template(
    soc2_type2_sections_factory: SOC2Type2SectionsFactory,
):
    assert soc2_type2_sections_factory.create_section_3() is None


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.build_criteria_table',
    return_value=dict(),
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_4_without_template(
    build_criteria_table_mock,
    get_requirements_by_args_mock,
    soc2_type2_sections_factory: SOC2Type2SectionsFactory,
):
    assert soc2_type2_sections_factory.create_section_4() is None
    build_criteria_table_mock.assert_called_once()
    get_requirements_by_args_mock.assert_called_once()


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_5_without_template(
    get_requirements_by_args_mock: Mock,
    soc2_type2_sections_factory: SOC2Type2SectionsFactory,
):
    assert soc2_type2_sections_factory.create_section_5() is None
    get_requirements_by_args_mock.assert_called_once()


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_1_with_template(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
):
    assert (
        soc2_type2_sections_factory_with_templates.create_section_1()['section']
        == SECTION_1
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_2_with_template(
    get_criteria_by_audit_id_mock: Mock,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
):
    assert (
        soc2_type2_sections_factory_with_templates.create_section_2()['section']
        == SECTION_2
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_3_with_template(
    get_requirements_by_args_mock,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
):
    assert (
        soc2_type2_sections_factory_with_templates.create_section_3()['section']
        == SECTION_3
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_3_with_past_audit_report(
    get_requirements_by_args_mock,
    audit: Audit,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
):
    mocked_report_type_1 = '''
    <html>
        <body>
            This will not be a part of the section three
            <h1 id="mcetoc_1fiubplrmme" class="pb_before">
                Section III: The test
            </h1>
            <p>
                This is the section three and is super long
            </p>
            <div id="section-IV-delimitator"></div>
            This will not be a part of the section three
        </body>
    </html>
    '''
    AuditStatus.objects.create(
        audit=audit,
        requested=True,
        initiated=True,
        fieldwork=True,
        in_draft_report=True,
        completed=True,
        draft_report_file_generated=File(
            name='report.html', file=io.BytesIO(mocked_report_type_1.encode())
        ),
    )

    create_section_result = (
        soc2_type2_sections_factory_with_templates.create_section_3()
    )
    assert create_section_result['section'] == SECTION_3


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.build_criteria_table',
    return_value=dict(),
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_4_with_template(
    build_criteria_table_mock,
    get_requirements_by_args_mock,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
):
    template = soc2_type2_sections_factory_with_templates.create_section_4()
    assert template['section'] == SECTION_4
    build_criteria_table_mock.assert_called_once()
    get_requirements_by_args_mock.assert_called_once()


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_5_with_template(
    get_requirements_by_args_mock,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
):
    template = soc2_type2_sections_factory_with_templates.create_section_5()
    assert template['section'] == SECTION_5
    get_requirements_by_args_mock.assert_called_once()


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_1_with_qualified_criteria(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    is_qualified_criteria: Criteria,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
    soc2_type2_section1: SOC2Type2Section1,
):
    assert soc2_type2_section1._generate_context()['has_qualified_criteria'] is True
    assert (
        soc2_type2_sections_factory_with_templates.create_section_1()['section']
        == SECTION_1
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_1_without_qualified_criteria(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    criteria: Criteria,
    audit_soc2_type2: Audit,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
    soc2_type2_section1: SOC2Type2Section1,
):
    assert soc2_type2_section1._generate_context()['has_qualified_criteria'] is False
    assert (
        soc2_type2_sections_factory_with_templates.create_section_1()['section']
        == SECTION_1
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_2_with_qualified_criteria(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    is_qualified_criteria: Criteria,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
    soc2_type2_section2: SOC2Type2Section2,
):
    assert soc2_type2_section2._generate_context()['has_qualified_criteria'] is True
    assert (
        soc2_type2_sections_factory_with_templates.create_section_2()['section']
        == SECTION_2
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_2_without_qualified_criteria(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    criteria: Criteria,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
    soc2_type2_section2: SOC2Type2Section2,
):
    assert soc2_type2_section2._generate_context()['has_qualified_criteria'] is False
    assert (
        soc2_type2_sections_factory_with_templates.create_section_2()['section']
        == SECTION_2
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_1_system_name(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    is_qualified_criteria: Criteria,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
    soc2_type2_section1: SOC2Type2Section1,
):
    assert (
        soc2_type2_section1._generate_context()['system_name']
        == ORGANIZATION_SYSTEM_NAME
    )
    assert (
        soc2_type2_sections_factory_with_templates.create_section_1()['section']
        == SECTION_1
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_create_section_2_system_name(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    is_qualified_criteria: Criteria,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
    soc2_type2_section2: SOC2Type2Section2,
):
    assert (
        soc2_type2_section2._generate_context()['system_name']
        == ORGANIZATION_SYSTEM_NAME
    )
    assert (
        soc2_type2_sections_factory_with_templates.create_section_2()['section']
        == SECTION_2
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_3_system_name(
    get_requirements_by_args_mock,
    soc2_type2_sections_factory_with_templates: SOC2Type2SectionsFactory,
    soc2_type2_section3: SOC2Type2Section3,
):
    assert (
        soc2_type2_section3._generate_context()['system_name']
        == ORGANIZATION_SYSTEM_NAME
    )
    assert (
        soc2_type2_sections_factory_with_templates.create_section_3()['section']
        == SECTION_3
    )
