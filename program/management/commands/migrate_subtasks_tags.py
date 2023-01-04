import codecs
import csv

from django.core.management.base import BaseCommand
from django.db import transaction

from laika.aws.s3 import s3_client
from program.models import SubTask
from tag.models import Tag


class Command(BaseCommand):
    help = '''
        Migrate subtasks to link new tags to them.
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
            organization_id = row.get('organization_id')
            task_id = row.get('task_id')
            subtask_id = row.get('subtask_id')
            tags = row.get('tags')
            link_subtask_tags(organization_id, task_id, subtask_id, tags, self.stdout)

    def get_file_rows(self, bucket_name, file_name):
        try:
            s3_response_object = s3_client.get_object(Bucket=bucket_name, Key=file_name)
            return csv.DictReader(codecs.getreader('utf-8')(s3_response_object['Body']))
        except Exception as e:
            self.stdout.write(f'There was a problem reading the file {file_name}')
            self.stdout.write(f'The error was: {e}')


def link_subtask_tags(organization_id, task_id, subtask_id, tags, log):
    log.write('------------------------------------------------------')
    log.write(
        f'Linking organization: {organization_id} '
        f'subtask: {subtask_id} with tags: {tags}'
    )
    log.write()

    try:
        with transaction.atomic():
            subtask = SubTask.objects.filter(
                id=subtask_id,
                task_id=task_id,
                task__program__organization_id=organization_id,
            ).first()

            if not subtask:
                log.write(
                    f'Subtask: {subtask_id} not found for '
                    f'organization {organization_id}'
                )
                return

            tags_strings = [t.strip() for t in tags.split(',')] if tags else []
            tags_list = []
            for t in tags_strings:
                tag, _ = Tag.objects.get_or_create(
                    organization_id=organization_id, name=t
                )
                tags_list.append(tag)

            if not len(tags_list):
                return

            subtask.tags.add(*tags_list)
            log.write(
                f'Migrating subtask: {subtask_id} tags was completed successfully'
            )
    except Exception as e:
        log.write(f'Migration failed for subtask {subtask_id}')
        log.write(f'Something bad happened: {e}')
    log.write('------------------------------------------------------')
