import logging

from laika.celery import app as celery_app
from report.models import Report

logger = logging.getLogger('reports_tasks')


@celery_app.task(name='Generate Report PDF')
def generate_report_pdf(report_id, organization_id):
    logger.info(f'Generating report PDF for report with id: {report_id}')
    report = Report.objects.get(id=report_id, owner__organization=organization_id)
    report.pdf_file = report.create_pdf_file()
    report.save()

    logger.info(f'PDF file generated for report with id: {report_id}')
