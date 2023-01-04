import enum
import io
import logging
import os
import tempfile
import uuid

import django.template
import pdfkit
from bs4 import BeautifulSoup
from django.core.files import File
from django.db import models
from django.forms import model_to_dict
from django.template import Context, loader
from django.utils.text import slugify

from laika.settings import DJANGO_SETTINGS
from laika.storage import PrivateMediaStorage
from laika.utils import pdf
from link.models import Link
from organization.models import REPORT_FIELDS, Organization
from policy.models import Policy
from user.models import Officer, Team, User

logger = logging.getLogger('reports')

API_URL = DJANGO_SETTINGS.get('LAIKA_APP_URL')


class OwnerOrderBy(enum.Enum):
    FIELD = 'owner'
    FIRST_NAME = 'owner__first_name'
    LAST_NAME = 'owner__last_name'


LINK_FIELDS = ['is_enabled', 'expiration_date']


def template_file_directory_path(instance, filename):
    return f'{instance.organization.id}/templates/{instance.name}/{filename}'


def report_file_directory_path(instance, filename):
    organization_id = instance.template.organization.id
    return f'{organization_id}/reports/{instance.name}/{filename}'


class Template(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=512, default='')
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='templates'
    )
    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=template_file_directory_path,
        blank=True,
        max_length=1024,
    )

    def __str__(self):
        return self.name


class ReportQuerySet(models.QuerySet):
    def sort(self, order_by):
        if not order_by:
            return self.order_by('-display_id')

        order = '-' if order_by.get('order') == 'descend' else ''
        field = order_by.get('field')

        if field == OwnerOrderBy.FIELD.value:
            order_by_first = order + OwnerOrderBy.FIRST_NAME.value
            return self.order_by(order_by_first, OwnerOrderBy.LAST_NAME.value)

        if field in LINK_FIELDS:
            return self.order_by(order + 'link__' + field)

        return self.order_by(order + field)


class ReportManager(models.Manager):
    _queryset_class = ReportQuerySet


def get_table_of_contents(contents):
    root = BeautifulSoup(f'<div class="page-content">{contents}</div>', features='lxml')
    headers = root.findAll(['h1', 'h2'])
    headers_hierarchy = get_headers_hierarchy(headers)
    toc_html = headers_hierarchy_to_html(root, headers_hierarchy)
    return root.div.prettify(), toc_html.prettify()


def get_headers_hierarchy(headers):
    toc = []
    h1_prev = 0
    for header in headers:
        try:
            if not header.get('id'):
                # add the id to the header element
                header['id'] = slugify(header.string)

            # tuple with id used in href and and text for the link
            data = [(header.get('id'), header.text)]

            if header.name == "h1":
                toc.append(data)
                h1_prev = len(toc) - 1
            elif header.name == "h2":
                toc[int(h1_prev)].append(data)
        except (AttributeError, LookupError):
            logger.warning(
                f'Error creating table of contents element for: {header.string}'
            )
    return toc


def headers_hierarchy_to_html(root, headers_list, nested=False):
    ul = root.new_tag('ul')
    li = None
    if nested:
        ul['class'] = 'nested'

    for item in headers_list:
        if isinstance(item, list):
            if li is None:
                # First UL, no headers processed yet
                ul.append(headers_hierarchy_to_html(root, item))
                ul['id'] = 'contents-list'
            else:
                li.append(headers_hierarchy_to_html(root, item, True))
        else:
            li = root.new_tag('li')
            ul.append(li)
            if has_nested_ul(headers_list):
                append_expandable_header(root, li, item)
            else:
                append_header_link(root, li, item)
    return ul


def has_nested_ul(headers_list):
    return len(headers_list) != 1


def append_header_link(root, li, item):
    link = root.new_tag('a')
    link['href'] = f'#{item[0]}'
    li.append(link)
    div = root.new_tag('div')
    div['class'] = 'contents-label'
    link.append(div)
    span = root.new_tag('span')
    span['class'] = 'no-caret'
    span.string = item[1]
    div.append(span)


def append_expandable_header(root, li, item):
    div = root.new_tag('div')
    div['class'] = 'contents-label'
    li.append(div)
    img = root.new_tag('img')
    img['class'] = 'caret'
    div.append(img)
    span = root.new_tag('span')
    span.string = item[1]
    div.append(span)


class Report(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=250, default='')
    display_id = models.IntegerField(blank=True)
    token = models.UUIDField(default=uuid.uuid4)

    owner = models.ForeignKey(
        User,
        related_name='user_report',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    link = models.OneToOneField(
        Link, on_delete=models.CASCADE, related_name='report', blank=True, null=True
    )

    template = models.ForeignKey(
        Template,
        related_name='reports',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    pdf_file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=report_file_directory_path,
        blank=True,
        max_length=1024,
    )

    html_file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=report_file_directory_path,
        blank=True,
        max_length=1024,
    )

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def _increment_display_id(self):
        # Get the maximum display_id value from the database
        last_id = Report.objects.filter(
            owner__organization=self.owner.organization
        ).aggregate(largest=models.Max('display_id'))['largest']

        if last_id is not None:
            self.display_id = last_id + 1
        else:
            self.display_id = 1

    def _create_link(self):
        return Link.objects.create(
            organization=self.owner.organization,
            url=f'{API_URL}/report/{self.id}?token={self.token}',
            expiration_date=None,
        )

    def create_pdf_file(self):
        context = self.get_report_context()

        cover_template = loader.render_to_string('report/report_cover.html', context)
        header_template = loader.render_to_string('report/report_header.html', context)
        footer_template = loader.render_to_string('report/report_footer.html', context)
        report_template = loader.render_to_string('report/report_pdf.html', context)
        options = {
            'page-size': 'Letter',
            'header-spacing': 20,
            'footer-spacing': 18,
            'dpi': 72,
            # This flag tells wkhtmltopdf to use the @media print css rules.
            'print-media-type': '',
        }
        cover_pdf = pdfkit.from_string(cover_template, False, options)

        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as header_html:
            options['header-html'] = header_html.name
            header_html.write(header_template.encode('utf-8'))

        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as footer_html:
            options['footer-html'] = footer_html.name
            footer_html.write(footer_template.encode('utf-8'))

        template_pdf = pdfkit.from_string(report_template, False, options=options)
        report_pdf = pdf.merge(cover_pdf, template_pdf)
        os.remove(options['footer-html'])
        return File(name=f'{os.path.basename(self.name)}.pdf', file=report_pdf)

    def _create_html_file(self):
        context = self.get_report_context()
        report_html = loader.render_to_string('report/report.html', context)
        return File(
            name=f'{os.path.basename(self.name)}.html',
            file=io.BytesIO(report_html.encode()),
        )

    def get_report_context(self):
        if not self.template:
            raise ValueError(f'Template not found for report: {self.id}')

        template_text = self.template.file.read().decode('utf-8')
        template = django.template.Template(template_text)
        self.template.file.seek(0)

        base_context = self.get_base_context()
        contents = template.render(Context(base_context))

        updated_contents, table_of_contents = get_table_of_contents(contents)
        base_context['table_of_contents'] = table_of_contents
        context = {**base_context, 'report_content': updated_contents}
        return context

    def get_base_context(self):
        organization = self.template.organization
        officers = Officer.objects.filter(organization_id=organization).values(
            'name', 'description'
        )

        teams = Team.objects.filter(organization=organization).values(
            'name', 'description'
        )

        policies = (
            Policy.objects.filter(organization=organization, is_published=True)
            .order_by('display_id')
            .values('name', 'description', 'display_id')
        )

        return {
            'organization': model_to_dict(organization, fields=REPORT_FIELDS),
            'name': self.name,
            'date': self.created_at.strftime("%B %Y"),
            'policies': policies,
            'officers': officers,
            'teams': teams,
        }

    def save(self, *args, **kwargs):
        name_duplicated = (
            Report.objects.filter(
                name=self.name, owner__organization=self.owner.organization
            )
            .exclude(id=self.id)
            .exists()
        )

        if name_duplicated:
            raise ValueError('Duplicated report name in organization')

        if self._state.adding:
            self._increment_display_id()
            super(Report, self).save(*args, **kwargs)
            self.link = self._create_link()
            self.html_file = self._create_html_file()
        super(Report, self).save()

    objects = ReportManager()


class DaysOrderBy(enum.Enum):
    FIELD = 'time'
    FILTERS = [('LAST_SEVEN_DAYS', 7), ('LAST_MONTH', 30), ('LAST_QUARTER', 120)]
