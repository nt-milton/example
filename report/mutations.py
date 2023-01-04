import logging
import uuid

import graphene
from django.db import transaction

from laika.auth import login_required, permission_required
from laika.utils.exceptions import ServiceException, service_exception
from laika.utils.history import create_revision
from link.models import Link
from report.constants import MAX_REPORT_NAME_LENGTH
from report.inputs import CreateReportInput, ToggleReportInput
from report.models import Report, Template
from report.tasks import generate_report_pdf

logger = logging.getLogger('reports')


class CreateReport(graphene.Mutation):
    class Arguments:
        input = CreateReportInput(required=True)

    id = graphene.Int()

    @login_required
    @service_exception('Cannot create a new report')
    @create_revision('Created new report')
    @permission_required('report.add_report')
    def mutate(self, info, input):
        organization = info.context.user.organization
        if not Template.objects.filter(
            organization=organization,
        ).exists():
            raise ServiceException(
                'Error creating the report. You do not have templates yet.'
            )

        template = Template.objects.filter(
            organization=organization,
        ).first()

        name = input.get('name', '')
        if len(name) > MAX_REPORT_NAME_LENGTH:
            raise ServiceException(
                'Error creating the report. Name length max is '
                f'{MAX_REPORT_NAME_LENGTH}.'
            )

        try:
            report = input.to_model(
                name=name,
                template=template,
                token=uuid.uuid4(),
                owner=info.context.user,
            )

            generate_report_pdf.delay(report.id, info.context.user.organization_id)
        except ValueError:
            raise ServiceException(f'Report "{name}" already exists.')
        return CreateReport(id=report.id)


class ToggleReport(graphene.Mutation):
    class Arguments:
        input = ToggleReportInput(required=True)

    id = graphene.String()

    @login_required
    @transaction.atomic
    @service_exception('Failed to edit report. Please try again.')
    @permission_required('report.delete_report')
    @create_revision('Soft delete report')
    def mutate(self, info, input):
        report = Report.objects.get(
            id=input.report_id, owner__organization=info.context.user.organization
        )
        report_name = report.name
        report.is_deleted = input.value

        if input.value:
            report_count = Report.objects.filter(name__icontains=report_name).count()
            delete_termination = f' - Deleted #{report_count+1}'
            new_report_name = f'{report_name}{delete_termination}'
            if len(new_report_name) > MAX_REPORT_NAME_LENGTH:
                new_report_name = f'{report_name[:232]}...{delete_termination}'
            report.name = new_report_name
            link = Link.objects.get(id=report.link.id)
            link.is_enabled = False
            link.save()
        else:
            report.name = report_name.split('-')[0]

        report.save()

        logger.info(f'Report {report.id} was edited')
        return ToggleReport(id=report.id)
