import json
from datetime import datetime

from django.http.response import HttpResponse, HttpResponseBadRequest
from django.template import loader
from django.views.decorators.csrf import csrf_exempt

from audit.models import Audit
from fieldwork.models import Attachment, Requirement
from laika.auth import login_required
from laika.decorators import audit_service
from laika.utils.files import get_file_extension
from laika.utils.pdf import convert_html_text_to_pdf

from .utils import (
    build_criteria_table,
    get_sso_cloud_provider,
    get_sso_cloud_providers_quantity,
    get_trust_service_categories,
    save_content_audit_draft_report_file,
)

LAIKA_PAPER_EXTENSION = '.laikapaper'


def download_attachment(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    attachment_id = body_obj.get('attachmentId')
    evidence_id = body_obj.get('evidenceId')

    if not attachment_id or not evidence_id:
        return HttpResponseBadRequest()

    attachment = Attachment.objects.get(id=attachment_id, evidence_id=evidence_id)

    response = HttpResponse(attachment.file, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment;filename="{attachment.name}"'

    file_extension = get_file_extension(attachment.name)
    if file_extension.lower() == LAIKA_PAPER_EXTENSION:
        pdf = convert_html_text_to_pdf(attachment.file.read().decode('utf-8'))
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment;filename="{attachment.name}.pdf"'

    return response


@csrf_exempt
@login_required
def export_attachment(request):
    return download_attachment(request)


@csrf_exempt
@audit_service(
    atomic=False,
    permission='fieldwork.view_attachment',
    exception_msg='Failed to download attachment',
)
def export_attachment_auditor(request):
    return download_attachment(request)


def get_requirement_description_for_report(display_id: str, audit_id: str) -> str:
    requirement = Requirement.objects.filter(
        display_id=display_id,
        audit_id=audit_id,
        is_deleted=False,
        exclude_in_report=False,
    ).first()

    return requirement.description if requirement else ''


@csrf_exempt
@audit_service(
    atomic=False,
    permission='audit.change_audit',
    exception_msg='Failed to generate report',
)
def generate_report(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('auditId')

    audit = Audit.objects.get(id=audit_id)
    organization = audit.organization

    criterias = build_criteria_table(audit_id)

    all_criteria = (
        criterias['control_environment']
        + criterias['communication_information']
        + criterias['risk_assessment']
        + criterias['monitoring_activities']
        + criterias['control_activities']
        + criterias['logical_physical_access']
        + criterias['system_operations']
        + criterias['change_management']
        + criterias['risk_mitigation']
        + criterias['additional_criteria_availability']
        + criterias['additional_criteria_confidentiality']
        + criterias['additional_criteria_processing_integrity']
        + criterias['additional_criteria_privacy']
    )

    audit_configuration = audit.audit_configuration
    context = {
        'client': organization.name,
        'audit_type': audit.audit_type,
        'company_legal_name': organization.legal_name,
        'as_of_date': datetime.strptime(audit_configuration['as_of_date'], '%Y-%m-%d'),
        'TSCs': get_trust_service_categories(
            audit_configuration['trust_services_categories']
        ),
        'TSC_list': audit_configuration['trust_services_categories'],
        'category_copy': 'categories'
        if len(audit_configuration['trust_services_categories']) > 1
        else 'category',
        'sso_cloud_provider': get_sso_cloud_provider(organization),
        'sso_cloud_providers_quantity': get_sso_cloud_providers_quantity(organization),
        'company_logo': organization.logo.url if organization.logo else None,
        'LCL_5': get_requirement_description_for_report('LCL-5', audit_id),
        'LCL_13': get_requirement_description_for_report('LCL-13', audit_id),
        'LCL_46': get_requirement_description_for_report('LCL-46', audit_id),
        'LCL_20': get_requirement_description_for_report('LCL-20', audit_id),
        'LCL_45': get_requirement_description_for_report('LCL-45', audit_id),
        'control_environment_table': criterias['control_environment'],
        'communication_information_table': criterias['communication_information'],
        'risk_assessment_table': criterias['risk_assessment'],
        'monitoring_activities_table': criterias['monitoring_activities'],
        'control_activities_table': criterias['control_activities'],
        'logical_physical_access_table': criterias['logical_physical_access'],
        'system_operations_table': criterias['system_operations'],
        'change_management_table': criterias['change_management'],
        'risk_mitigation_table': criterias['risk_mitigation'],
        'additional_criteria_availability_table': criterias[
            'additional_criteria_availability'
        ],
        'additional_criteria_confidentiality_table': criterias[
            'additional_criteria_confidentiality'
        ],
        'additional_criteria_processing_integrity_table': criterias[
            'additional_criteria_processing_integrity'
        ],
        'additional_criteria_privacy_table': criterias['additional_criteria_privacy'],
        'has_criteria': len(all_criteria) > 0,
    }

    template = loader.get_template('SOC-report-template.html')

    template_content = template.render(context)

    save_content_audit_draft_report_file(
        audit=audit, organization=organization, content=template_content
    )

    return HttpResponse(status=200)
