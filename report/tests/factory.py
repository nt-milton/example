import datetime
import io
import os
import tempfile
from datetime import datetime as dt
from datetime import timedelta

from django.core.files import File

from report.models import Report, Template
from user.tests import create_user


def create_organization_logo(organization):
    organization.logo = File(
        name='mock.png',
        file=tempfile.TemporaryFile(),
    )
    organization.save()


def create_reports(organization):
    today = datetime.datetime.now()
    today = dt.combine(today, dt.min.time()) + timedelta(hours=24)

    create_organization_logo(organization)

    user_a = create_user(
        organization, permissions=['report.view_report'], email='test_a@heylaika.com'
    )
    user_a.first_name = 'Test_First_A'
    user_a.last_name = 'Test_Last_A'
    user_a.save()

    user_b = create_user(
        organization, permissions=['report.view_report'], email='test_b@heylaika.com'
    )
    user_b.first_name = 'Test_First_B'
    user_b.last_name = 'Test_Last_B'
    user_b.save()

    report_a = Report.objects.create(
        name='Test_Report_A', owner=user_a, template=create_template(organization)
    )
    report_a.link.expiration_date = today
    report_a.link.is_enabled = False
    report_a.link.save()

    report_b = Report.objects.create(
        name='Test_Report_B', owner=user_b, template=create_template(organization)
    )
    report_b.link.expiration_date = today + datetime.timedelta(days=1)
    report_b.link.is_enabled = True
    report_b.link.save()

    return report_a, report_b


def create_report(organization, name='', owner=None):
    create_organization_logo(organization)
    return Report.objects.create(
        name=name, owner=owner, template=create_template(organization)
    )


def create_template(organization, name='Reports Template.pdf', file=None):
    if not file:
        file = File(
            name=f'{name}.pdf',
            file=tempfile.TemporaryFile(),
        )
    return Template.objects.create(organization=organization, name=name, file=file)


def create_template_with_content(organization):
    html_template = '''
        <p><img style=\"display: block; margin-left: auto;"
           margin-right: auto;\"
           src=\"https://laika-static-documents.s3.amazonaws.com/Logos/Spur\"
           alt=\"\" width=\"200\" height=\"200\" />
        </p>
        \n<h1 style=\"text-align:
        center;\"><span style=\"font-family: helvetica, arial, sans-serif;\">
        <strong>Inventory List</strong>
        </p>
    '''
    name = 'Template Test 1'
    template_file = File(
        name=f'{os.path.basename(name)}.html', file=io.BytesIO(html_template.encode())
    )
    template = Template.objects.create(
        organization=organization, name=name, file=template_file
    )
    return template
