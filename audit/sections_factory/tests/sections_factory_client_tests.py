import io
from unittest.mock import Mock, patch

import pytest
from django.core.files import File

from audit.constants import SECTION_1, SECTION_2, SECTION_3, SECTION_4, SECTION_5
from audit.models import FrameworkReportTemplate
from audit.sections_factory.sections_factory_client import SectionFactoryClient
from audit.sections_factory.SOC2_Type2_sections_factory import SOC2Type2SectionsFactory
from audit.tests.constants import CRITERIA_MOCK_DATA
from fieldwork.models import Criteria, Requirement

FILE_NAME = 'file_test.html'


@pytest.fixture
def soc2_type2_sections_factory_client(audit_soc2_type2):
    return SectionFactoryClient(audit=audit_soc2_type2)


@pytest.fixture
def soc2_type1_sections_factory_client(audit_soc2_type1):
    return SectionFactoryClient(audit=audit_soc2_type1)


@pytest.fixture
def soc2_type2_sections_factory_client_with_templates(audit_soc2_type2):
    audit_soc2_type2.audit_framework_type.templates.add(
        FrameworkReportTemplate(
            name='Section I: This is a test',
            section=SECTION_1,
            file=File(
                file=io.BytesIO('This is content for the section 1'.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section II: This is a test section 2',
            section=SECTION_2,
            file=File(
                file=io.BytesIO('This is content for the section 2'.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section V: This is a test section 5',
            section=SECTION_5,
            file=File(
                file=io.BytesIO('This is content for the section 5'.encode()),
                name=FILE_NAME,
            ),
        ),
        bulk=False,
    )
    return SectionFactoryClient(audit=audit_soc2_type2)


@pytest.fixture
def soc2_type1_sections_factory_client_with_templates(audit_soc2_type1):
    audit_soc2_type1.audit_framework_type.templates.add(
        FrameworkReportTemplate(
            name='Section I: This is a test',
            section=SECTION_1,
            file=File(
                file=io.BytesIO('This is content for section 1 template'.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section III: This is a test',
            section=SECTION_3,
            file=File(
                file=io.BytesIO('This is content for section 3 template'.encode()),
                name=FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section IV: This is a test',
            section=SECTION_4,
            file=File(
                file=io.BytesIO('This is content for section 4 template'.encode()),
                name=FILE_NAME,
            ),
        ),
        bulk=False,
    )
    return SectionFactoryClient(audit=audit_soc2_type1)


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.build_criteria_table',
    return_value=dict(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_soc2_type2_audit_client(
    get_criteria_by_audit_id_mock,
    utils_get_requirements_by_args_mock,
    factory_get_requirements_by_args_mock,
    build_criteria_table_mock,
    soc2_type2_sections_factory_client: SectionFactoryClient,
):
    assert (
        isinstance(soc2_type2_sections_factory_client.factory, SOC2Type2SectionsFactory)
        is True
    )
    assert len(soc2_type2_sections_factory_client.generate_all_sections()) == 0


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_generate_section_1_without_template(
    get_requirements_by_args_mock,
    get_criteria_by_audit_id_mock,
    soc2_type2_sections_factory_client: SectionFactoryClient,
):
    assert soc2_type2_sections_factory_client.generate_section(SECTION_1) is None


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_generate_section_2_without_template(
    get_criteria_by_audit_id_mock: Mock,
    soc2_type2_sections_factory_client: SectionFactoryClient,
):
    assert soc2_type2_sections_factory_client.generate_section(SECTION_2) is None


@pytest.mark.functional
def test_generate_section_3_without_template(
    soc2_type2_sections_factory_client: SectionFactoryClient,
):
    assert soc2_type2_sections_factory_client.generate_section(SECTION_3) is None


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.build_criteria_table',
    return_value=dict(),
)
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_generate_section_4_without_template(
    utils_get_requirements_by_args_mock,
    factory_get_requirements_by_args_mock,
    build_criteria_table_mock,
    soc2_type2_sections_factory_client: SectionFactoryClient,
):
    assert soc2_type2_sections_factory_client.generate_section(SECTION_4) is None


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_generate_section_5_without_template(
    get_requirements_by_args_mock: Mock,
    soc2_type2_sections_factory_client: SectionFactoryClient,
):
    assert soc2_type2_sections_factory_client.generate_section(SECTION_5) is None
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
def test_generate_section_1_with_template(
    get_requirements_by_args_mock: Mock,
    get_criteria_by_audit_id_mock: Mock,
    soc2_type2_sections_factory_client_with_templates: SectionFactoryClient,
):
    assert (
        soc2_type2_sections_factory_client_with_templates.generate_section(SECTION_1)[
            'section'
        ]
        == SECTION_1
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_criteria_by_audit_id',
    return_value=Criteria.objects.all(),
)
def test_generate_section_2_with_template(
    get_criteria_by_audit_id_mock: Mock,
    soc2_type2_sections_factory_client_with_templates: SectionFactoryClient,
):
    assert (
        soc2_type2_sections_factory_client_with_templates.generate_section(SECTION_2)[
            'section'
        ]
        == SECTION_2
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_generate_section_5_with_template(
    get_requirements_by_args_mock: Mock,
    soc2_type2_sections_factory_client_with_templates: SectionFactoryClient,
):
    assert (
        soc2_type2_sections_factory_client_with_templates.generate_section(SECTION_5)[
            'section'
        ]
        == SECTION_5
    )
    get_requirements_by_args_mock.assert_called_once()


@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
@pytest.mark.functional
def test_generate_type_1_section_1_without_template(
    build_criteria_table_mock,
    soc2_type1_sections_factory_client: SectionFactoryClient,
):
    assert soc2_type1_sections_factory_client.generate_section(SECTION_1) is None
    build_criteria_table_mock.assert_called_once()


@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
@pytest.mark.functional
def test_generate_type_1_section_1_with_template(
    build_criteria_table_mock,
    soc2_type1_sections_factory_client_with_templates: SectionFactoryClient,
):
    assert (
        soc2_type1_sections_factory_client_with_templates.generate_section(SECTION_1)[
            'section'
        ]
        == SECTION_1
    )
    build_criteria_table_mock.assert_called_once()


@pytest.mark.functional
def test_generate_type_1_section_3_with_template(
    soc2_type1_sections_factory_client_with_templates: SectionFactoryClient,
):
    assert (
        soc2_type1_sections_factory_client_with_templates.generate_section(SECTION_3)[
            'section'
        ]
        == SECTION_3
    )


@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@pytest.mark.functional
def test_generate_type_1_section_4_with_template(
    get_requirements_by_args_mock,
    build_criteria_table_mock,
    soc2_type1_sections_factory_client_with_templates: SectionFactoryClient,
):
    assert (
        soc2_type1_sections_factory_client_with_templates.generate_section(SECTION_4)[
            'section'
        ]
        == SECTION_4
    )
    build_criteria_table_mock.assert_called_once()
    get_requirements_by_args_mock.assert_called_once()
