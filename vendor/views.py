import base64
import logging

from botocore.exceptions import ClientError
from django.db.models.fields.files import FieldFile
from django.http.response import HttpResponse
from django.views.decorators.http import require_GET

from laika.auth import login_required
from laika.utils.pdf import render_template_to_pdf

logger = logging.getLogger(__name__)


def file_to_base64(file: FieldFile):
    data = None
    try:
        data = file.read() if file else None
    except ClientError as err:
        logger.warning(f'{type(err)} {err}')
        data = None
    except OSError as err:
        logger.warning(f'{type(err)} {err}')
    except Exception as err:
        logger.error(f'{type(err)} {err}')

    base64_data = base64.b64encode(data).decode("UTF-8") if data else ""
    return base64_data


def get_printable_value(value):
    return value if value else '---'


def first_stakeholder_by_created_at(vendor):
    organization_stakeholder = vendor.internal_organization_stakeholders.order_by(
        'sort_index'
    ).first()

    return organization_stakeholder.stakeholder if organization_stakeholder else None


def get_vendors_pdf(organization, vendors, time_zone):
    context = {
        'organization_name': organization.name,
        'vendors': [
            {
                'name': ov.vendor.name,
                'admin': first_stakeholder_by_created_at(ov),
                'risk': get_printable_value(ov.risk_rating),
                'status': get_printable_value(ov.get_status_display()),
                'logo': file_to_base64(ov.vendor.logo),
                'certifications': [
                    file_to_base64(c.logo) for c in ov.vendor.certifications.all()
                ],
            }
            for ov in vendors
        ],
    }

    return render_template_to_pdf(
        template='vendors/organization_vendors.html',
        context=context,
        time_zone=time_zone,
    )


@require_GET
@login_required
def export_vendors(request):
    time_zone = request.GET.get('time_zone')
    organization = request.user.organization
    vendors = organization.organization_vendors.all()
    pdf = get_vendors_pdf(request.user.organization, vendors, time_zone)
    response = HttpResponse(pdf, content_type='application/pdf')
    response[
        'Content-Disposition'
    ] = f'attachment;filename="{request.user.organization.name}-vendors.pdf"'
    return response
