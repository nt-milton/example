import io
from unittest.mock import patch

import pytest
from django.core.files import File

from audit.constants import SECTION_1, SECTION_2, SECTION_3, SECTION_4
from audit.models import FrameworkReportTemplate
from audit.sections_factory.SOC2_Type1_sections_factory import SOC2Type1SectionsFactory
from audit.tests.constants import CRITERIA_MOCK_DATA
from fieldwork.models import Requirement


@pytest.fixture
def soc2_type1_sections_factory(audit_soc2_type1):
    return SOC2Type1SectionsFactory(audit=audit_soc2_type1)


TEST_FILE_NAME = 'file_test.html'


@pytest.fixture
def soc2_type1_sections_factory_with_templates(audit_soc2_type1):
    audit_soc2_type1.audit_framework_type.templates.add(
        FrameworkReportTemplate(
            name='Section I: This is a test section 1',
            section=SECTION_1,
            file=File(
                file=io.BytesIO('This is content for sec 1 template'.encode()),
                name=TEST_FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section II: This is a test section 2',
            section=SECTION_2,
            file=File(
                file=io.BytesIO('This is content for sec 2 template'.encode()),
                name=TEST_FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section III: This is a test section 3',
            section=SECTION_3,
            file=File(
                file=io.BytesIO('This is content for sec 3 template'.encode()),
                name=TEST_FILE_NAME,
            ),
        ),
        FrameworkReportTemplate(
            name='Section IV: This is a test section 4',
            section=SECTION_4,
            file=File(
                file=io.BytesIO('This is content for sec 4 template'.encode()),
                name=TEST_FILE_NAME,
            ),
        ),
        bulk=False,
    )
    return SOC2Type1SectionsFactory(audit=audit_soc2_type1)


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
def test_create_section_1_without_template_should_return_none(
    build_criteria_table_mock,
    soc2_type1_sections_factory: SOC2Type1SectionsFactory,
):
    assert soc2_type1_sections_factory.create_section_1() is None
    build_criteria_table_mock.assert_called_once()


@pytest.mark.functional
def test_create_section_2_without_template_should_return_none(
    soc2_type1_sections_factory: SOC2Type1SectionsFactory,
):
    assert soc2_type1_sections_factory.create_section_2() is None


@pytest.mark.functional
def test_create_section_3_without_template_should_return_none(
    soc2_type1_sections_factory: SOC2Type1SectionsFactory,
):
    assert soc2_type1_sections_factory.create_section_3() is None


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_4_without_template_should_return_none(
    get_requirements_by_args_mock,
    build_criteria_table_mock,
    soc2_type1_sections_factory: SOC2Type1SectionsFactory,
):
    assert soc2_type1_sections_factory.create_section_4() is None
    build_criteria_table_mock.assert_called_once()
    get_requirements_by_args_mock.assert_called_once()


@pytest.mark.functional
def test_create_section_5_should_return_none(
    soc2_type1_sections_factory: SOC2Type1SectionsFactory,
):
    assert soc2_type1_sections_factory.create_section_5() is None


@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
@pytest.mark.functional
def test_create_section_1_with_template(
    build_criteria_table_mock,
    soc2_type1_sections_factory_with_templates: SOC2Type1SectionsFactory,
):
    assert (
        soc2_type1_sections_factory_with_templates.create_section_1()['section']
        == SECTION_1
    )
    build_criteria_table_mock.assert_called_once()


@pytest.mark.functional
def test_create_section_2_with_template(
    soc2_type1_sections_factory_with_templates: SOC2Type1SectionsFactory,
):
    assert (
        soc2_type1_sections_factory_with_templates.create_section_2()['section']
        == SECTION_2
    )


@pytest.mark.functional
def test_create_section_3_with_template(
    soc2_type1_sections_factory_with_templates: SOC2Type1SectionsFactory,
):
    assert (
        soc2_type1_sections_factory_with_templates.create_section_3()['section']
        == SECTION_3
    )


@pytest.mark.functional
@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_create_section_4_with_template(
    get_requirements_by_args_mock,
    build_criteria_table_mock,
    soc2_type1_sections_factory_with_templates: SOC2Type1SectionsFactory,
):
    assert (
        soc2_type1_sections_factory_with_templates.create_section_4()['section']
        == SECTION_4
    )
    build_criteria_table_mock.assert_called_once()
    get_requirements_by_args_mock.assert_called_once()
