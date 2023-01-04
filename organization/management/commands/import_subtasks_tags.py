import codecs
import csv

from django.core.management.base import BaseCommand
from django.db import transaction

from laika.aws.s3 import s3_client
from organization.models import SubtaskTag


class Command(BaseCommand):
    help = '''
        Import subtasks texts and tags to be
        used later for linking with organizations
        subtasks.
        The command looks for a file within the
        organization-subtask-tags bucket,
        you need to provide a file-name attribute
        with the name of the file
        stored in the bucket.
    '''

    def add_arguments(self, parser):
        parser.add_argument('--file-name', type=str)
        parser.add_argument('--bucket-name', type=str)

    def handle(self, *args, **options):
        bucket_name = options.get('bucket_name')
        file_name = options.get('file_name')
        rows = self.get_file_rows(bucket_name, file_name)
        for row in rows:
            subtask_text = row.get('subtask_text').strip()
            tags = row.get('tags', '').strip().lower()
            import_subtask_tags(subtask_text, tags, self.stdout)

    def get_file_rows(self, bucket_name, file_name):
        try:
            s3_response_object = s3_client.get_object(Bucket=bucket_name, Key=file_name)
            return csv.DictReader(codecs.getreader('utf-8')(s3_response_object['Body']))
        except Exception as e:
            self.stdout.write(f'There was a problem reading the file {file_name}')
            self.stdout.write(f'The error was: {e}')


def import_subtask_tags(subtask_text, tags, log):
    log.write('------------------------------------------------------')
    log.write(f'Importing subtask: {subtask_text} tags: {tags}')
    log.write()

    try:
        with transaction.atomic():
            SubtaskTag.objects.update_or_create(
                subtask_text=subtask_text, defaults={'tags': tags}
            )

            log.write(
                f'Importing subtask: {subtask_text} tags was completed successfully'
            )
    except Exception as e:
        log.write(f'Importing failed for subtask {subtask_text}')
        log.write(f'Something bad happened: {e}')
    log.write('------------------------------------------------------')
