import logging

from django.views.decorators.csrf import csrf_exempt

from laika.auth import login_required
from laika.utils.schema_builder.template_builder import TemplateBuilder
from library.constants import LibraryTemplateSchema

LIBRARY_XLSX = 'Library.xlsx'

logger = logging.getLogger(__name__)


@csrf_exempt
@login_required
def export_library_template(request):
    try:
        builder = TemplateBuilder(schemas=[LibraryTemplateSchema])
        return builder.build_response(LIBRARY_XLSX)
    except Exception as e:
        logger.exception(
            'Error exporting library template for organization: '
            f'{request.user.organization}. Error: {e}'
        )
