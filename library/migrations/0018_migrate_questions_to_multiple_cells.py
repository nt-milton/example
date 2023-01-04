# Generated by Django 3.1.12 on 2022-02-15 14:54
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def migrate_library_metadata(apps, schema_editor):
    question_model = apps.get_model('library', 'Question')
    questions = question_model.objects.all()

    for question in questions:
        try:
            if question.metadata.get('answerAddress'):
                question.metadata = {
                    'sheet': question.metadata.get('sheet'),
                    'answerAddresses': [question.metadata.get('answerAddress')],
                    'questionAddress': question.metadata.get('questionAddress'),
                }
        except Exception as err:
            logger.warning(
                f'Error updating question metadata: {question.id}Error: {err}'
            )

    question_model.objects.bulk_update(questions, ['metadata'])


class Migration(migrations.Migration):
    dependencies = [
        ('library', '0017_add_questionnaire_alert'),
    ]

    operations = [
        migrations.RunPython(
            migrate_library_metadata, reverse_code=migrations.RunPython.noop
        )
    ]
