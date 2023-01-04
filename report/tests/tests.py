import datetime

import pytest

from organization.tests import create_organization
from policy.models import Policy
from report.models import Report
from report.tests.factory import create_report, create_reports
from user.models import Officer, Team
from user.tests import create_user

TEST_REPORT_A = 'Test_Report_A'
TEST_REPORT_B = 'Test_Report_B'


@pytest.fixture
def organization():
    return create_organization()


@pytest.fixture()
def user(organization):
    return create_user(organization, [], 'laika@heylaika.com')


#
# Display ID Increment Tests
#


@pytest.mark.django_db
def test_auto_display_id(organization):
    create_reports(organization)
    filtered_reports = Report.objects.filter(owner__organization=organization).sort(
        {'order': 'ascend', 'field': 'owner'}
    )

    assert filtered_reports[0].display_id == 1
    assert filtered_reports[1].display_id == 2


#
# QuerySet Custom Sort Tests
#


@pytest.mark.django_db
def test_sort_by_owner_asc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'ascend', 'field': 'owner'})
        .first()
    )

    assert report.name == TEST_REPORT_A


@pytest.mark.django_db
def test_sort_by_owner_desc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'descend', 'field': 'owner'})
        .first()
    )

    assert report.name == TEST_REPORT_B


@pytest.mark.django_db
def test_sort_by_display_asc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'ascend', 'field': 'display_id'})
        .first()
    )

    assert report.name == TEST_REPORT_A


@pytest.mark.django_db
def test_sort_by_display_desc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'descend', 'field': 'display_id'})
        .first()
    )

    assert report.name == TEST_REPORT_B


@pytest.mark.django_db
def test_sort_by_name_asc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'ascend', 'field': 'name'})
        .first()
    )

    assert report.name == TEST_REPORT_A


@pytest.mark.django_db
def test_sort_by_name_desc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'descend', 'field': 'name'})
        .first()
    )

    assert report.name == TEST_REPORT_B


# TODO: LK-2886 - Uncomment these tests
@pytest.mark.django_db
def test_sort_by_is_enabled_asc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'ascend', 'field': 'is_enabled'})
        .first()
    )

    assert report.name == TEST_REPORT_A


@pytest.mark.django_db
def test_sort_by_is_enabled_desc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'descend', 'field': 'is_enabled'})
        .first()
    )

    assert report.name == TEST_REPORT_B


@pytest.mark.django_db
def test_sort_by_expiration_date_asc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'ascend', 'field': 'expiration_date'})
        .first()
    )

    assert report.name == TEST_REPORT_A


@pytest.mark.django_db
def test_sort_by_expiration_date_desc(organization):
    create_reports(organization)
    report = (
        Report.objects.filter(owner__organization=organization)
        .sort({'order': 'descend', 'field': 'expiration_date'})
        .first()
    )

    assert report.name == TEST_REPORT_B


#
# Report Creation tests
#


@pytest.mark.django_db
def test_template_missing(organization, user):
    with pytest.raises(ValueError) as ex:
        Report.objects.create(name='No Template Report', owner=user)
    assert str(ex.value) == 'Template not found for report: 1'


@pytest.mark.django_db
def test_report_link_created(organization, user):
    report = create_report(organization, TEST_REPORT_A, user)
    assert report.link is not None


@pytest.mark.django_db
def test_html_report_created(organization, user):
    report = create_report(organization, TEST_REPORT_A, user)
    assert report.html_file is not None
    assert f'{TEST_REPORT_A}.html' in report.html_file.name


@pytest.mark.django_db
def test_pdf_report_created(organization, user):
    report = create_report(organization, TEST_REPORT_A, user)
    # pdf_file is not created but has value of <FieldFile: None>
    assert not report.pdf_file.name

    pdf_file = report.create_pdf_file()
    assert f'{TEST_REPORT_A}.pdf' in pdf_file.name


#
# Report Base Context tests
#


@pytest.mark.django_db
def test_base_context(organization, user):
    today = datetime.date.today()
    report = create_report(organization, TEST_REPORT_A, user)

    organization.name = 'Organization name'
    organization.description = 'Organization description'
    organization.website = 'Organization website'
    organization.number_of_employees = 10
    organization.business_inception_date = today
    organization.product_or_service_description = 'Organization service'

    Officer.objects.create(
        name='Officer Name',
        description='Officer Description',
        organization=organization,
    )

    Team.objects.create(
        name='Team Name', description='Team Description', organization=organization
    )

    Policy.objects.create(
        name='Policy Name',
        description='Policy Description',
        organization=organization,
        is_published=True,
    )

    base_context = report.get_base_context()
    context_org = base_context['organization']
    service_description = context_org['product_or_service_description']
    assert context_org['name'] == 'Organization name'
    assert context_org['description'] == 'Organization description'
    assert context_org['website'] == 'Organization website'
    assert context_org['number_of_employees'] == 10
    assert context_org['business_inception_date'] == today
    assert service_description == 'Organization service'
    assert context_org.get('id') is None

    context_officer = base_context['officers'][0]
    assert context_officer['name'] == 'Officer Name'
    assert context_officer['description'] == 'Officer Description'
    assert context_officer.get('id') is None

    context_team = base_context['teams'][0]
    assert context_team['name'] == 'Team Name'
    assert context_team['description'] == 'Team Description'
    assert context_team.get('id') is None

    context_policy = base_context['policies'][0]
    assert context_policy['display_id'] == 1
    assert context_policy['name'] == 'Policy Name'
    assert context_policy['description'] == 'Policy Description'
    assert context_policy.get('id') is None
