import logging

from django.db import models, transaction

from program.constants import SUBTASK_DOCUMENTATION, SUBTASK_PRIORITY_DEFAULT
from program.models import (
    Program,
    SubTask,
    SubtaskCertificationSection,
    SubtaskTag,
    Tag,
    Task,
)
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_certification_by_name,
    get_certification_section,
    get_certifications_keys,
    get_headers,
    should_process_sheet,
)
from seeder.seeders.tasks import create_task_initials, create_task_number
from user.models import User

logger = logging.getLogger('seeder')


SUBTASK_REQUIRED_FIELDS = ['program_name', 'task_name', 'text']

SUBTASK_FIELDS = [
    'program_name',
    'task_name',
    'text',
    'assignee_email',
    'group',
    'requires_evidence',
    'sort_index',
    'priority',
    'due_date',
    'tags',
    'badges',
    'complexity_group',
    'complexity',
    'subtask_reference_id',
]


def associate_subtask_tags(organization, tag_names, subtask):
    tags_objs = []
    for t in tag_names:
        tag, _ = Tag.objects.get_or_create(
            name=t.strip(), organization_id=organization.id
        )
        if not SubtaskTag.objects.filter(tag=tag, subtask=subtask).exists():
            tags_objs.append(SubtaskTag(tag=tag, subtask=subtask))
    SubtaskTag.objects.bulk_create(objs=tags_objs)


def get_subtask_from_list(subtasks, text, task_name):
    for s in subtasks:
        if s.text == text and s.task.name == task_name:
            return s


def associate_section_names(certification, subtask, section_names):
    certification_sections = []
    for section in section_names:
        if section:
            cert_section = get_certification_section(section, certification)
            certification_sections.append(
                SubtaskCertificationSection(
                    subtask=subtask, certification_section=cert_section
                )
            )
    return certification_sections


def associate_certificates(dictionary, subtask):
    certifications_dic = get_certifications_keys(dictionary, SUBTASK_FIELDS)
    for key in certifications_dic:
        certification = get_certification_by_name(key)
        if certification and certifications_dic[key]:
            certification_sections = associate_section_names(
                certification, subtask, certifications_dic[key].split(',')
            )
            SubtaskCertificationSection.objects.bulk_create(objs=certification_sections)


def insert_subtasks_relations(organization, subtasks_sheet, headers, subtasks):
    subtask_relation_error = []
    for row in subtasks_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))
        if are_columns_empty(dictionary, SUBTASK_REQUIRED_FIELDS):
            continue
        try:
            subtask = get_subtask_from_list(
                subtasks, dictionary['text'], dictionary['task_name'].strip()
            )
            if dictionary['tags']:
                associate_subtask_tags(
                    organization, dictionary['tags'].split(','), subtask
                )
            associate_certificates(dictionary, subtask)
        except Exception as e:
            subtask_relation_error.append(
                f'Subtask in row {row[0].row}: has failed. {e}'
            )
            logger.exception(f'Subtask in row: {row[0].row} has failed. {e}')
    return subtask_relation_error


def get_value_from_column_or_default(workbook_columns, column_name, default_value):
    if column_name in workbook_columns:
        return workbook_columns[column_name] or default_value
    return default_value


def seed(organization, workbook):
    status_detail = []

    if not should_process_sheet(workbook, 'sub-tasks'):
        return status_detail

    subtasks_sheet = workbook['sub-tasks']
    headers = get_headers(subtasks_sheet)
    subtasks = []
    for row in subtasks_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))
        if are_columns_empty(dictionary, SUBTASK_REQUIRED_FIELDS):
            continue
        try:
            with transaction.atomic():
                if are_columns_required_empty(dictionary, SUBTASK_REQUIRED_FIELDS):
                    status_detail.append(
                        'Error seeding subtask with text: '
                        f'{dictionary["text"]}. '
                        f'Fields: {SUBTASK_REQUIRED_FIELDS} are required.'
                    )
                    continue

                if 'complexity_group' in dictionary and 'complexity' not in dictionary:
                    status_detail.append(
                        'Error seeding subtask with text: '
                        f'{dictionary["text"]}. '
                        'Field: complexity is required if complexity_group '
                        'is given.'
                    )
                    continue

                logger.info(f'Program name related >> {dictionary["program_name"]}')
                program = Program.objects.get(
                    name=dictionary['program_name'].strip(), organization=organization
                )

                assignee = None
                if dictionary['assignee_email']:
                    assignee, _ = User.objects.get_or_create(
                        email=dictionary['assignee_email'],
                        organization=organization,
                        defaults={
                            'role': '',
                            'last_name': '',
                            'first_name': '',
                            'is_active': False,
                            'username': '',
                        },
                    )

                logger.info(f'Task name related >> {dictionary["task_name"]}')
                task = Task.objects.get(
                    program=program, name=dictionary['task_name'].strip()
                )

                evidence = get_value_from_column_or_default(
                    dictionary, 'requires_evidence', False
                )
                priority = get_value_from_column_or_default(
                    dictionary, 'priority', SUBTASK_PRIORITY_DEFAULT
                )
                complexity_group = get_value_from_column_or_default(
                    dictionary, 'complexity_group', ''
                )
                group = get_value_from_column_or_default(
                    dictionary, 'group', SUBTASK_DOCUMENTATION
                )
                due_date = get_value_from_column_or_default(
                    dictionary, 'due_date', None
                )
                badges = get_value_from_column_or_default(dictionary, 'badges', '')
                complexity = get_value_from_column_or_default(
                    dictionary, 'complexity', None
                )
                subtask, created = SubTask.objects.update_or_create(
                    text=dictionary['text'],
                    task=task,
                    defaults={
                        'assignee': assignee,
                        'group': group,
                        'requires_evidence': evidence,
                        'sort_index': dictionary['sort_index'],
                        'priority': priority,
                        'due_date': due_date,
                        'badges': badges,
                        'complexity_group': complexity_group,
                        'complexity': complexity,
                        'customer_identifier': create_subtask_initials(task, group),
                        'number': create_subtask_number(task),
                        'reference_id': reference_id(dictionary),
                    },
                )

                subtasks.append(subtask)
        except Exception as e:
            logger.warning(
                f'Subtask: {dictionary["text"]} has failed.\n'
                f'Error {e}. \nRow {row[0].row}.'
            )
            status_detail.append(
                f'Error seeding subtask: {dictionary["text"]}. \n'
                f'Row: {row[0].row}. Error: {e}'
            )
    # insert relations with tags, certifications section names
    subtask_relation_error = insert_subtasks_relations(
        organization, subtasks_sheet, headers, subtasks
    )
    status_detail.extend(subtask_relation_error)
    return status_detail


def reference_id(r):
    return get_value_from_column_or_default(r, 'subtask_reference_id', None)


def create_subtask_initials(task, group):
    initials = create_task_initials(task.category)
    return (
        initials
        + str(create_task_number(initials, task.program))
        + '-'
        + group[0].upper()
        + str(create_subtask_number(task))
    )


def create_subtask_number(task):
    last_number = SubTask.objects.filter(task=task).aggregate(
        largest=models.Max('number')
    )['largest']

    if last_number is not None:
        return last_number + 1
    return 0
