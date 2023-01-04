from django.core.management.base import BaseCommand, CommandError

from laika.legacy import migrate_all_tasks_document_evidence, migrate_task_files
from organization.models import Organization


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('organization_ids', nargs='+', type=str)

    def handle(self, *args, **options):
        for organization_id in options['organization_ids']:
            try:
                organization = Organization.objects.get(id=organization_id)
            except Organization.DoesNotExist:
                raise CommandError(f'Organization {organization_id} does not exist')

            bucket_name = f'org-{organization.id}'
            evidence_path = 'evidence'
            migrate_task_files(organization, bucket_name, evidence_path)
            migrate_all_tasks_document_evidence(organization)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Organization {organization.id} task evidence migrated'
                )
            )
