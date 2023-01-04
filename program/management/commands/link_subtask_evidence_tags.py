from django.core.management.base import BaseCommand
from django.db import transaction

from program.models import SubTask


class Command(BaseCommand):
    help = '''
        Linking subtask tags to their related evidence.
    '''

    def add_arguments(self, parser):
        parser.add_argument('--organization-ids', nargs='+', type=str)

    def handle(self, *args, **options):
        link_evidence_subtask_tags(options, self.stdout)


def link_evidence_subtask_tags(options, log):
    log.write('------------------------------------------------------')
    with transaction.atomic():
        for organization_id in options['organization_ids']:
            subtasks = SubTask.objects.filter(
                task__program__organization_id=organization_id
            )

            for subtask in subtasks:
                try:
                    if not subtask.has_evidence:
                        continue

                    log.write(
                        f'Linking subtask: {subtask.id} tags to evidence'
                        f' for organization: {organization_id}'
                    )

                    for e in subtask.evidence.all():
                        e.tags.add(*subtask.tags.all())
                except Exception as e:
                    log.write(
                        'Linking subtasks tags to evidence failed'
                        f' for organization: {organization_id}'
                    )
                    log.write(f'Something bad happened: {e}')
                    continue
                log.write('------------------------------------------------------')
