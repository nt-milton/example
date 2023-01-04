import logging

from django.db import migrations, models

from library.constants import FETCH_STATUS, NO_RESULT, NOT_RAN, RESULT_FOUND

logger = logging.getLogger(__name__)


def migrate_question_fetched_status(apps, schema_editor):
    question_model = apps.get_model('library', 'Question')
    questions = question_model.all_objects.iterator()
    questions_to_update = []

    for question in questions:
        try:
            if question.questionnaires.all().count() > 0:
                if question.fetched is False:
                    question.fetch_status = NO_RESULT
                else:
                    question.fetch_status = RESULT_FOUND

                questions_to_update.append(question)

        except Exception as err:
            logger.error(
                f'Error migrating fetch_status from question: {question.id} '
                f'Error: {err}'
            )

    try:
        question_model.objects.bulk_update(questions_to_update, ['fetch_status'])
    except Exception as err:
        logger.error(f'Error updating questionError: {err}')


class Migration(migrations.Migration):
    dependencies = [
        ('library', '0026_alter_question_managers'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='fetch_status',
            field=models.CharField(
                default=NOT_RAN, choices=FETCH_STATUS, max_length=21
            ),
        ),
        migrations.RunPython(
            migrate_question_fetched_status, reverse_code=migrations.RunPython.noop
        ),
    ]
