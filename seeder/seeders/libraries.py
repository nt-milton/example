import logging
from datetime import datetime

from library.models import LibraryEntry, Question
from library.utils import (
    LIBRARY_FIELDS,
    LIBRARY_REQUIRED_FIELDS,
    are_questions_valid,
    create_question,
    is_category_valid,
)
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('seeder')


class Library(Seeder):
    def __init__(self, organization, workbook):
        logger.info(f'Seeding libraries for organization: {organization.id}')
        self._organization = organization
        self._workbook = workbook
        self._sheet_name = 'library'
        self._fields = LIBRARY_FIELDS
        self._required_fields = LIBRARY_REQUIRED_FIELDS
        self._required_error_msg = (
            'Error seeding library.Fields: answer, question, category, are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        logger.info('Processing libraries')
        dictionary = self._dictionary

        category = dictionary['category'].strip()

        if not is_category_valid(category):
            self._status_detail.append(
                'Error seeding library with question: '
                f'{dictionary["question"]}, '
                'Field: category not valid.'
            )
            return

        question = dictionary['question'].strip()
        organization = self._organization
        stored_question = Question.objects.filter(
            text=question, library_entry__organization=organization, default=True
        )
        aliases = self._other
        all_questions = [question] + aliases

        if stored_question.exists():
            # Make an update of the library entry
            entry = stored_question.first().library_entry
            questions_valid = are_questions_valid(organization, question, aliases)
            if not questions_valid:
                self._status_detail.append(
                    'Error seeding library, '
                    'duplicated questions found:'
                    f' {all_questions}'
                )
                return

            entry.answer_text = dictionary['answer']
            entry.short_answer_text = dictionary['short_answer']
            entry.category = category
            # This is because in case a question is updated,
            # the entry updated_at would not be updated
            entry.updated_at = datetime.now()
            entry.save()
            # Upserting aliases to existing questions
            if len(aliases):
                for q in aliases:
                    Question.objects.update_or_create(
                        text=q, default=False, library_entry=entry
                    )
        else:
            # create new library entry
            duplicated_exists = Question.objects.filter(
                text__in=all_questions, library_entry__organization=organization
            ).exists()

            if duplicated_exists or question in aliases:
                self._status_detail.append(
                    'Error seeding library, '
                    'duplicated questions found:'
                    f' {all_questions}'
                )
                return

            entry_payload = {
                'answer_text': dictionary['answer'],
                'short_answer_text': dictionary['short_answer'],
                'category': category,
                'organization': organization,
            }
            default_entry = LibraryEntry.objects.create(**entry_payload)
            default_question = create_question(default_entry, question, default=True)

            for question_text in aliases:
                entry = LibraryEntry.objects.create(**entry_payload)
                new_question = create_question(entry, question_text)
                default_question.equivalent_questions.add(new_question)

    def _process_exception(self, e):
        logger.exception(f'Library: {self._dictionary["question"]} has failed.', e)
        self._status_detail.append(
            f'Error seeding libraries: {self._dictionary["question"]}.Error: {e}'
        )
