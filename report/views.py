import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from laika.auth import login_required
from laika.settings import CSP_RULE
from report.models import Report

from .tasks import generate_report_pdf

logger = logging.getLogger('reports')


@csrf_exempt
def get_report_template(request, report_id):
    token = request.GET.get('token', '')
    logger.info(f'Internal report request {report_id}')
    if not token or not report_id:
        return HttpResponse('Unauthorized', status=401)
    try:
        report = Report.objects.get(id=report_id, token=token)

        response = HttpResponse(report.html_file)
        response['Content-Security-Policy'] = CSP_RULE
        return response

    except Report.DoesNotExist:
        logger.warning(f'Report not found with ID {report_id}')
        return HttpResponse('Incorrect Request', status=400)

    except Exception:
        logger.error(f'Error getting the report with ID {report_id}')
        return HttpResponse('Incorrect Request', status=400)


def _pdf_response(template):
    response = HttpResponse(template.file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment;filename="{template.name}.pdf"'
    return response


@csrf_exempt
@login_required
def export_pdf_report(request):
    user = request.user
    organization_id = user.organization_id
    body_obj = json.loads(request.body.decode('utf-8'))
    report_id = body_obj.get('reportId')
    logger.info(f'Internal report request {report_id}')
    try:
        report = Report.objects.get(id=report_id, owner__organization=organization_id)
        if not report.pdf_file:
            generate_report_pdf.delay(report_id, organization_id)
            return HttpResponse('report exists but PDF file was not found', status=404)

        response = HttpResponse(report.pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment;filename={report.name}".pdf"'
        return response
    except Report.DoesNotExist:
        logger.warning(
            f'Report id not found {report_id} for organization: {organization_id}'
        )
        return HttpResponse('Report not found', status=404)
