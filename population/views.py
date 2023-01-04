import json
import logging

from django.http.response import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from openpyxl import Workbook

from laika.auth import login_required
from laika.backends.audits_backend import AuditAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import laika_service, service
from laika.utils.files import get_file_extension
from laika.utils.schema_builder.template_builder import TemplateBuilder
from laika.utils.spreadsheet import CONTENT_TYPE, save_virtual_workbook
from population.models import AuditPopulation, PopulationCompletenessAccuracy
from population.population_builder.schemas import POPULATION_SCHEMAS

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
@laika_service(
    permission='population.view_auditpopulation',
    exception_msg='Could not download audit population file',
    revision_name='Download audit population file',
)
def download_population_file(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    population_id = body_obj.get('id')

    if not population_id:
        return HttpResponseBadRequest()
    population = AuditPopulation.objects.get(id=population_id)

    file = population.data_file

    file_extension = get_file_extension(str(file.file))
    response = HttpResponse(file, content_type='application/octet-stream')
    file_name = f'{population.name}{file_extension}'
    response['Content-Disposition'] = f'attachment;filename="{file_name}"'
    return response


def get_response(filename, workbook):
    response = HttpResponse(
        content=save_virtual_workbook(workbook), content_type=CONTENT_TYPE
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def to_upper_snake_case(value: str) -> str:
    return value.upper().replace(' ', '_')


def get_population_template_filename(population_name: str) -> str:
    return f'POP_{to_upper_snake_case(population_name)}_TEMPLATE.xlsx'


@csrf_exempt
@require_POST
@login_required
def export_population_template(request):
    body = json.loads(request.body.decode('utf-8'))
    population_display_id = body.get('populationDisplayId')

    if not population_display_id:
        return HttpResponseBadRequest()

    schema = POPULATION_SCHEMAS.get(population_display_id)
    filename = get_population_template_filename(schema.sheet_name)
    try:
        builder = TemplateBuilder(schemas=[schema])
        return builder.build_response(filename)
    except Exception as e:
        logger.exception(
            'Error exporting population template for organization: '
            f'{request.user.organization}. Error: {e}'
        )

    return get_response(filename, Workbook())


@csrf_exempt
@require_POST
@service(
    allowed_backends=[
        {
            'backend': AuthenticationBackend.BACKEND,
            'permission': 'population.view_populationcompletenessaccuracy',
        },
        {
            'backend': AuditAuthenticationBackend.BACKEND,
            'permission': 'population.view_populationcompletenessaccuracy',
        },
    ],
    exception_msg='Could not download completeness and accuracy file',
)
def download_completeness_and_accuracy_file(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('auditId')
    population_id = body_obj.get('populationId')
    file_id = body_obj.get('fileId')

    if not audit_id or not population_id or not file_id:
        return HttpResponseBadRequest()

    completeness_and_accuracy = PopulationCompletenessAccuracy.objects.get(
        id=file_id, population_id=population_id, population__audit_id=audit_id
    )

    file = completeness_and_accuracy.file

    response = HttpResponse(file, content_type='application/octet-stream')
    response[
        'Content-Disposition'
    ] = f'attachment;filename="{completeness_and_accuracy.name}"'
    return response
