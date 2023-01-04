import logging
import threading
from datetime import datetime, timedelta

import django.utils.timezone as timezone
import pytz
from django.core.files import File
from django.db import transaction

from laika.aws.ses import send_email
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from laika.utils.dates import MMMM_DD_YYYY, format_iso_date
from link.models import Link

API_URL = DJANGO_SETTINGS.get('LAIKA_APP_URL')

logger = logging.getLogger('evidence')


class BulkEvidenceExportThread(threading.Thread):
    def __init__(self, async_export_request, evidence, **kwargs):
        logger.info(f'Bulk exporting {len(evidence)} files')

        self.async_export_request = async_export_request
        self.evidence = evidence

        super(BulkEvidenceExportThread, self).__init__(**kwargs)

    def expiration_date(self):
        expiration = self.async_export_request.link.url.split('Expires=')
        if len(expiration) > 1:
            return datetime.utcfromtimestamp(int(expiration[1][:10])).replace(
                tzinfo=pytz.UTC
            )
        return self.async_export_request.created_at(tz=timezone.utc) + timedelta(
            hours=1
        )

    @transaction.atomic
    def run(self):
        try:
            logger.info(
                'Async export evidence request for organization:'
                f' {self.async_export_request.organization.id}'
                f' and request: {self.async_export_request.id}'
            )
            zip_buffer = self.evidence.export()

            self.async_export_request.link = File(
                name=f'{self.async_export_request.name}.zip', file=zip_buffer
            )
            self.async_export_request.save()

            expiration = self.expiration_date()

            link = Link.objects.create(
                organization=self.async_export_request.organization,
                url=f'{self.async_export_request.link.url}',
                expiration_date=expiration,
                time_zone=self.async_export_request.time_zone,
                is_enabled=True,
            )

            self.async_export_request.link_model = link
            self.async_export_request.save()

            logger.info(
                'Delivering email for export evidence request:'
                f' {self.async_export_request.id}'
            )

            export_type = self.async_export_request.export_type.lower()
            entity = (
                self.async_export_request.name.title()
                if type == 'dataroom'
                else self.async_export_request.organization.name
            )

            context = {
                'finished_date': format_iso_date(
                    self.async_export_request.created_at, MMMM_DD_YYYY
                ),
                'files_length': len(self.async_export_request.evidence.all()),
                'entity': entity,
                'type': export_type,
                'file_link': link.public_url,
            }
            send_email(
                subject='Your Laika Files are Ready!',
                from_email=NO_REPLY_EMAIL,
                to=[self.async_export_request.requested_by.email],
                template='export_evidence_link.html',
                template_context=context,
            )

            self.async_export_request.delivered = True
            self.async_export_request.save()
        except Exception as e:
            logger.exception(
                'Error when exporting evidence for request:'
                f' {self.async_export_request.id}. {e}'
            )
            self.async_export_request.errors = e
            self.async_export_request.save()
