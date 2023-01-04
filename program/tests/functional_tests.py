import tempfile

import pytest
from django.core.files import File

from certification.tests import create_certificate_sections_list, create_certification
from control.models import Control
from control.tests.factory import create_control
from drive.models import DriveEvidence, DriveEvidenceData
from evidence.models import TagEvidence
from program.constants import SUBTASK_DOCUMENTATION, SUBTASK_GROUP, SUBTASK_STATUS
from program.models import Program, SubTask, Task
from program.tests import (
    ADD_SUBTASK_EVIDENCE,
    GET_ORGANIZATION_PROGRAMS,
    GET_PROGRAM_ALL_CERTIFICATES,
    GET_PROGRAM_CERTIFICATES,
    GET_PROGRAM_DETAIL_QUERY,
    GET_PROGRAM_TASKS,
    GET_PROGRAMS_QUERY,
    GET_SUBTASK_QUERY,
    GET_TASK_DETAILS_QUERY,
    GET_TASK_SUBTASK_QUERY,
    UPDATE_PROGRAM,
    UPDATE_SUBTASK,
    UPDATE_SUBTASK_ASSIGNEE,
    UPDATE_SUBTASK_DUE_DATE,
    UPDATE_SUBTASK_STATUS,
    associate_certification_sections_to_subtask,
    associate_task_to_program,
    create_program,
    create_task,
)
from program.utils.task_numbers import (
    create_task_initials,
    populate_subtask_numbers,
    populate_task_numbers,
)
from tag.models import Tag
from user.constants import ROLE_SUPER_ADMIN
from user.tests import create_user

ISO_FORMAT = '%Y-%m-%d'

CTRL_NAME = 'CTRL-1'
SOC2_TYPE_2 = 'SOC 2 Type 2'
ISO_27001 = 'ISO 27001'
USER_TEST_EMAIL = 'john@heylaika.com'

DOCUMENTATION_GROUP = 0
FIRST_SUBTASK = 0
SECOND_SUBTASK = 1
EVIDENCE_DICT = 0
SPACE = ' '

SUBTASK_TEXT = 'Subtask 1'


@pytest.fixture
def program(graphql_organization):
    return create_program(
        organization=graphql_organization,
        name='Privacy Program',
        description='This is an example of program',
    )


@pytest.fixture
def task(graphql_organization, program):
    return create_task(organization=graphql_organization, program=program)


@pytest.fixture
def control(graphql_organization):
    return Control.objects.create(organization=graphql_organization, name=CTRL_NAME)


@pytest.fixture
def subtask_1(task, graphql_organization):
    subtask = SubTask.objects.create(
        task=task,
        text=SUBTASK_TEXT,
        status='completed',
        group='documentation',
        sort_index=1,
        badges='technical',
    )

    subtask_tag = Tag.objects.create(
        name='Subtask Tag',
        organization=graphql_organization,
    )
    subtask.tags.add(subtask_tag)
    return subtask


@pytest.fixture
def subtask_2(task):
    return SubTask.objects.create(
        task=task, text='Subtask 2', group='policy', sort_index=2
    )


@pytest.fixture
def user_test(graphql_organization):
    return create_user(
        graphql_organization,
        email=USER_TEST_EMAIL,
        role=ROLE_SUPER_ADMIN,
        first_name='john',
    )


@pytest.mark.functional(permissions=['program.change_subtask_partial'])
def test_update_subtask_status(graphql_client, subtask_1):
    subtask_id = str(subtask_1.id)

    graphql_client.execute(
        UPDATE_SUBTASK_STATUS,
        variables={
            'input': dict(
                id=subtask_id, status='not_applicable', completedAt='2021-02-5'
            )
        },
    )
    updated_subtask = SubTask.objects.get(id=subtask_id)
    assert updated_subtask.status == 'not_applicable'


@pytest.mark.functional(permissions=['program.change_subtask_partial'])
def test_update_subtask_due_date(graphql_client, subtask_1):
    subtask_id = str(subtask_1.id)

    graphql_client.execute(
        UPDATE_SUBTASK_DUE_DATE,
        variables={'input': dict(id=subtask_id, dueDate='2021-01-21')},
    )
    updated_subtask = SubTask.objects.get(id=subtask_id)
    due_date = updated_subtask.due_date
    assert due_date.strftime(ISO_FORMAT) == '2021-01-21'


@pytest.mark.functional(permissions=['program.change_subtask_partial'])
def test_update_subtask_due_date_clear(graphql_client, subtask_1):
    subtask_id = str(subtask_1.id)
    subtask_1.due_date = '2021-01-21'
    subtask_1.save()

    graphql_client.execute(
        UPDATE_SUBTASK_DUE_DATE, variables={'input': dict(id=subtask_id, dueDate=None)}
    )
    updated_subtask = SubTask.objects.get(id=subtask_id)
    assert updated_subtask.due_date is None


@pytest.mark.functional(permissions=['program.change_subtask_partial'])
def test_update_subtask_assignee(graphql_client, subtask_1, user_test):
    subtask_id = str(subtask_1.id)
    graphql_client.execute(
        UPDATE_SUBTASK_ASSIGNEE,
        variables={'input': dict(id=subtask_id, assigneeEmail=USER_TEST_EMAIL)},
    )
    updated_subtask = SubTask.objects.get(id=subtask_id)
    assert updated_subtask.assignee is not None
    assert updated_subtask.assignee.email == USER_TEST_EMAIL


@pytest.mark.functional(permissions=['program.change_program'])
def test_update_program_unassigned_program_lead(graphql_client, program):
    program_id = str(program.id)
    graphql_client.execute(UPDATE_PROGRAM, variables={'input': dict(id=program_id)})

    updated_program = Program.objects.get(id=program_id)
    assert updated_program.program_lead is None


@pytest.mark.functional(permissions=['program.change_program'])
def test_update_program(graphql_client, program, user_test):
    program_id = str(program.id)
    graphql_client.execute(
        UPDATE_PROGRAM,
        variables={'input': dict(id=program_id, programLeadEmail=USER_TEST_EMAIL)},
    )

    updated_program = Program.objects.get(id=program_id)
    assert updated_program.program_lead.email == USER_TEST_EMAIL


@pytest.mark.functional(permissions=['program.view_program'])
def test_programs_query(
    graphql_client, graphql_organization, program, task, subtask_1, subtask_2
):
    soc2_sections = ['CC1.1', 'CC2.2']
    iso_sections = ['2.1', '3.1']
    soc2_cert_sections = create_certification(
        graphql_organization, soc2_sections, name=SOC2_TYPE_2
    ).sections.all()

    iso_cert_sections = create_certification(
        graphql_organization, iso_sections, name=ISO_27001, unlock_certificate=False
    ).sections.all()

    associate_certification_sections_to_subtask(subtask_1, soc2_cert_sections)
    associate_certification_sections_to_subtask(subtask_2, iso_cert_sections)
    associate_task_to_program(program, [task])
    control_one = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        status='IMPLEMENTED',
    )
    control_two = create_control(
        organization=graphql_organization, display_id=1, name='Control Test'
    )
    soc2_cert_sections.first().controls.add(control_one)
    iso_cert_sections.first().controls.add(control_one)
    iso_cert_sections.first().controls.add(control_two)
    executed = get_graph_query_programs_executed(graphql_client)

    programs = executed['data']['programs']
    assert programs[0]['allCertificatesCount'] == 2
    assert len(programs[0]['certifications']) == 2
    assert programs[0]['certifications'][0]['isLocked'] is False
    assert programs[0]['certifications'][1]['isLocked'] is True
    assert programs[0]['certifications'][0]['progress'] == 100
    assert programs[0]['certifications'][1]['progress'] == 50
    assert len(programs) == 1


@pytest.mark.functional(permissions=['program.view_program'])
def test_program_details_query(
    graphql_client, graphql_organization, program, task, subtask_1
):
    soc2_cert_sections = create_certification(
        graphql_organization, ['CC1.1', 'CC2.2'], name=SOC2_TYPE_2
    ).sections.all()

    task_2 = create_task(
        graphql_organization,
        program,
        'Task Not Visible',
        'Task without subtasks unlocked',
    )

    associate_certification_sections_to_subtask(subtask_1, soc2_cert_sections)
    associate_task_to_program(program, [task, task_2])
    executed = graphql_client.execute(
        GET_PROGRAM_TASKS, variables={'id': str(program.id)}
    )

    program_data = executed['data']['programTasks']
    assert program_data['tasks'][0]['name'] == 'Getting Started'
    # Len should be only one because task_2 is not visible since does not
    # have subtasks associated.
    assert len(program_data['tasks'][0]['tasks']) == 1


@pytest.mark.functional(permissions=['program.view_program'])
def test_program_details_query_with_visible_tasks(
    graphql_client, graphql_organization, program, task, subtask_1
):
    soc2_cert_sections = create_certification(
        graphql_organization, ['CC1.1', 'CC2.2'], name=SOC2_TYPE_2
    ).sections.all()

    task_2 = create_task(
        graphql_organization, program, 'Task Visible', 'Task with subtasks unlocked'
    )

    subtask_unlocked = SubTask.objects.create(
        task=task_2, text='Subtask Test', group='documentation'
    )

    iso_cert_sections = create_certification(
        graphql_organization, ['2.1', '3.1'], name=ISO_27001, unlock_certificate=True
    ).sections.all()

    associate_certification_sections_to_subtask(subtask_1, soc2_cert_sections)
    associate_certification_sections_to_subtask(subtask_unlocked, iso_cert_sections)

    associate_task_to_program(program, [task, task_2])
    executed = graphql_client.execute(
        GET_PROGRAM_TASKS, variables={'id': str(program.id)}
    )
    program_data = executed['data']['programTasks']
    assert len(program_data['tasks'][0]['tasks']) == 2


@pytest.mark.functional(permissions=['program.view_task'])
def test_task_controls_query_empty_results(graphql_client, graphql_organization, task):
    executed = get_graph_query_executed(graphql_client, task)

    controls = executed['data']['taskControls']
    assert len(controls) == 0


@pytest.mark.functional(permissions=['program.view_task'])
def test_task_controls_query_with_same_certification_sections(
    graphql_client, graphql_organization, task, subtask_1, control
):
    sections = ['Certification-Section_1', 'Certification-Section_2']
    certification_sections = create_certification(
        graphql_organization, sections
    ).sections.all()

    associate_certification_sections_to_control(control, certification_sections)
    associate_certification_sections_to_subtask(subtask_1, certification_sections)
    executed = get_graph_query_executed(graphql_client, task)
    controls = executed['data']['taskControls']
    assert len(controls) == 1
    assert controls[0]['name'] == CTRL_NAME


@pytest.mark.functional(permissions=['program.view_task'])
def test_task_details(graphql_client, task):
    executed = get_graph_query_task_details_executed(graphql_client, task)
    task_data = executed['data']['task']
    assert task_data['name'] == 'Task 1'
    assert task_data['category'] == 'Other'


@pytest.mark.functional(permissions=['program.view_task'])
def test_get_subtask(graphql_client, subtask_1):
    executed = get_graph_query_subtask_executed(graphql_client, subtask_1)
    subtask_data = executed['data']['subtask']
    group = dict(SUBTASK_GROUP)
    status = dict(SUBTASK_STATUS)
    assert subtask_data['text'] == SUBTASK_TEXT
    assert subtask_data['status'] == status['completed']
    assert subtask_data['group'] == group[SUBTASK_DOCUMENTATION]
    assert 'technical' in subtask_data['badges']


@pytest.mark.functional(permissions=['program.view_task'])
def test_resolve_evidence(subtask_1, graphql_client, graphql_organization, user_test):
    subtask_1.is_system_subtask = False
    subtask_1.save()
    task = subtask_1.task

    evidence_file = File(file=tempfile.TemporaryFile(), name='evidence file 1.pdf')
    tag, _ = Tag.objects.get_or_create(
        organization=graphql_organization, name=str(subtask_1.id)
    )
    tags = {'system_tags': [tag]}
    drive_evidence_data = DriveEvidenceData(type='FILE', file=evidence_file, **tags)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=graphql_organization,
        owner=user_test,
        drive_evidence_data=drive_evidence_data,
    )

    evidence_created_at = str(
        drive_evidence.evidence.systemtagevidence_set.first().created_at
    )
    executed = get_graph_query_tasksubtask_executed(graphql_client, task)
    evidence_data = executed['data']['task']['subtasks']
    subtasks = evidence_data[DOCUMENTATION_GROUP]['subtasks']
    evidence = subtasks[FIRST_SUBTASK]['evidence'][EVIDENCE_DICT]
    system_tag_evidence_created_at = evidence['systemTagCreatedAt'].replace('T', SPACE)

    assert evidence_created_at == system_tag_evidence_created_at
    assert str(drive_evidence.evidence.id) == evidence['id']
    assert drive_evidence.evidence.name == evidence['name']


@pytest.mark.functional(permissions=['program.view_task'])
def test_resolve_certifications(
    graphql_client, graphql_organization, program, task, subtask_1, subtask_2
):
    soc2_sections = ['CC1.1', 'CC2.2']
    iso_sections = ['2.1', '3.1']
    soc2_cert_sections = create_certification(
        graphql_organization, soc2_sections, name=SOC2_TYPE_2
    ).sections.all()

    iso_cert_sections = create_certification(
        graphql_organization, iso_sections, name=ISO_27001, unlock_certificate=False
    ).sections.all()
    associate_certification_sections_to_subtask(subtask_1, soc2_cert_sections)
    associate_certification_sections_to_subtask(subtask_2, iso_cert_sections)
    associate_task_to_program(program, [task])

    executed_unlocked_certificate = get_graph_query_subtask_executed(
        graphql_client, subtask_1
    )
    executed_locked_certificate = get_graph_query_subtask_executed(
        graphql_client, subtask_2
    )
    unlocked_certificates = executed_unlocked_certificate['data']['subtask']
    locked_certificates = executed_locked_certificate['data']['subtask']
    subtask_1_certificates = unlocked_certificates['certifications']
    subtask_2_certificates = locked_certificates['certifications']

    assert subtask_2_certificates == []
    assert SOC2_TYPE_2 in subtask_1_certificates


@pytest.mark.functional(permissions=['program.view_task'])
def test_task_controls_query_with_distinct_certification_sections(
    graphql_client, graphql_organization, task, subtask_1, control
):
    sections = ['Certification-Section_3']
    certification_sections = create_certification(
        graphql_organization, sections
    ).sections.all()

    associate_certification_sections_to_subtask(subtask_1, certification_sections)
    executed = get_graph_query_executed(graphql_client, task)
    # Since control doesn't have certification section Certification-Section_3
    # associated, then we get 0
    controls = executed['data']['taskControls']
    assert len(controls) == 0


@pytest.mark.functional(permissions=['program.view_program'])
def test_query_get_program_detail(graphql_client, program):
    # Get the program detail information, only related to the program

    response = graphql_client.execute(
        GET_PROGRAM_DETAIL_QUERY, variables={'id': str(program.id)}
    )
    data = dict(response['data']['programDetail'])

    assert data['name'] == 'Privacy Program'
    assert data['progress'] == 0
    assert data['programLead'] is None


@pytest.mark.functional(permissions=['program.view_program'])
def test_query_get_program_certificates(
    graphql_client, graphql_organization, task, subtask_1, program
):
    # Get the list of the first 5 certificates associated to a program

    sections = create_certificate_sections_list(graphql_organization)
    associate_certification_sections_to_subtask(subtask_1, sections)
    associate_task_to_program(program, [task])

    response = graphql_client.execute(
        GET_PROGRAM_CERTIFICATES, variables={'id': str(program.id)}
    )
    data = dict(response['data']['programCertificates'])

    # Len it's 5 since it truncates the list to get the first 5 certs
    assert len(data['certificates']) == 5


@pytest.mark.functional(permissions=['program.view_program'])
def test_query_get_program_all_certificates(
    graphql_client, graphql_organization, task, subtask_1, program
):
    # Get the list of all certificates associated to a program

    sections = create_certificate_sections_list(graphql_organization)
    associate_certification_sections_to_subtask(subtask_1, sections)

    associate_task_to_program(program, [task])
    response = graphql_client.execute(
        GET_PROGRAM_ALL_CERTIFICATES, variables={'id': str(program.id)}
    )
    data = dict(response['data']['programCertificates'])

    # Len should be 6 since it returns  all certificates list
    assert len(data['allCertificates']) == 6


@pytest.mark.functional(permissions=['program.view_program'])
def test_query_program_tasks(
    graphql_client, graphql_organization, program, task, subtask_1
):
    # Get tasks related and visible in a program

    soc2_cert_sections = create_certification(
        graphql_organization, ['CC1.1', 'CC2.2'], name=SOC2_TYPE_2
    ).sections.all()

    task_2 = create_task(
        graphql_organization, program, 'Task Visible', 'Task with subtasks unlocked'
    )

    subtask_unlocked = SubTask.objects.create(
        task=task_2,
        text='Subtask Test',
        group='documentation',
        sort_index=2,
        badges='technical',
        is_system_subtask=False,
    )

    iso_cert_sections = create_certification(
        graphql_organization, ['2.1', '3.1'], name=ISO_27001, unlock_certificate=True
    ).sections.all()

    associate_certification_sections_to_subtask(subtask_1, soc2_cert_sections)
    associate_certification_sections_to_subtask(subtask_unlocked, iso_cert_sections)

    associate_task_to_program(program, [task, task_2])
    response = graphql_client.execute(
        GET_PROGRAM_TASKS, variables={'id': str(program.id)}
    )
    data = dict(response['data']['programTasks'])
    assert len(data['tasks'][0]['tasks']) == 2


@pytest.mark.functional()
def test_create_task_initials(task):
    my_category = 'My First Category'
    task_initials = 'MF'
    task.category = my_category
    initials = create_task_initials(task)
    assert initials == task_initials


@pytest.mark.functional()
def test_populate_task_numbers(graphql_organization, program):
    task = create_task(organization=graphql_organization, program=program)

    task.category = 'My Category'
    task.save()

    populate_task_numbers(Task)

    assert len(Task.objects.all()) == 1
    assert Task.objects.first().customer_identifier == 'MC1'


@pytest.mark.functional()
def test_populate_subtask_numbers(task):
    task.category = 'My Category'
    task.customer_identifier = 'MC1'
    task.save()

    SubTask.objects.create(
        task=task,
        text=SUBTASK_TEXT,
        status='completed',
        group='documentation',
        sort_index=1,
        badges='technical',
    )

    populate_subtask_numbers(SubTask)

    assert len(SubTask.objects.all()) == 1
    assert SubTask.objects.first().customer_identifier == 'MC1-D1'


@pytest.mark.functional(permissions=['program.change_subtask', 'program.add_subtask'])
def test_update_subtask_changing_due_date(
    graphql_client,
    subtask_1,
):
    subtask_1.due_date = '2021-01-21'
    subtask_1.save()

    update_subtask_input = {
        'input': dict(dueDate='2021-01-22', text=subtask_1.text, id=str(subtask_1.id))
    }

    graphql_client.execute(UPDATE_SUBTASK, variables=update_subtask_input)

    updated_subtask = SubTask.objects.get(id=subtask_1.id)
    assert updated_subtask.due_date.strftime(ISO_FORMAT) == '2021-01-22'


@pytest.mark.functional(permissions=['program.change_subtask', 'program.add_subtask'])
def test_update_subtask_clearing_due_date(
    graphql_client,
    subtask_1,
):
    subtask_1.due_date = '2021-01-21'
    subtask_1.save()

    update_subtask_input = {
        'input': dict(dueDate=None, text=subtask_1.text, id=str(subtask_1.id))
    }

    graphql_client.execute(UPDATE_SUBTASK, variables=update_subtask_input)

    updated_subtask = SubTask.objects.get(id=subtask_1.id)
    assert updated_subtask.due_date is None


@pytest.mark.functional(permissions=['program.change_subtask', 'program.add_subtask'])
def test_update_subtask_not_changing_due_date(
    graphql_client,
    subtask_1,
):
    subtask_1.due_date = '2021-01-21'
    subtask_1.save()

    update_subtask_input = {'input': dict(text=subtask_1.text, id=str(subtask_1.id))}

    graphql_client.execute(UPDATE_SUBTASK, variables=update_subtask_input)

    updated_subtask = SubTask.objects.get(id=subtask_1.id)
    assert updated_subtask.due_date.strftime(ISO_FORMAT) == '2021-01-21'


def get_graph_query_programs_executed(graphql_client):
    return graphql_client.execute(GET_PROGRAMS_QUERY)


def get_graph_query_task_details_executed(graphql_client, task):
    return graphql_client.execute(
        GET_TASK_DETAILS_QUERY, variables={'id': str(task.id)}
    )


def get_graph_query_subtask_executed(graphql_client, subtask):
    return graphql_client.execute(GET_SUBTASK_QUERY, variables={'id': str(subtask.id)})


def get_graph_query_tasksubtask_executed(graphql_client, task):
    return graphql_client.execute(
        GET_TASK_SUBTASK_QUERY, variables={'id': str(task.id)}
    )


def associate_certification_sections_to_control(control, certification_sections):
    control.certification_sections.set(certification_sections)


def get_graph_query_executed(graphql_client, task):
    return graphql_client.execute(
        '''
         query taskControls($id: UUID!) {
            taskControls(id: $id) {
                id
                displayId
                name
                description
                status
            }
          }
        ''',
        variables={'id': str(task.id)},
    )


def get_graph_archived_evidence_query_executed(graphql_client, task):
    return graphql_client.execute(
        '''
        query archivedEvidence($taskId: UUID!) {
            archivedEvidence(taskId: $taskId) {
                taskId
                collection {
                    id
                    name
                    updatedAt
                    extension
                    owner {
                        firstName
                        lastName
                        email
                    }
                }
            }
        }
        ''',
        variables={'taskId': str(task.id)},
    )


@pytest.mark.functional(permissions=['program.change_task_implementation_notes'])
def test_update_task_notes(graphql_client, graphql_organization, task):
    variables = {
        'input': {
            'id': str(task.id),
            'implementationNotes': '<p>task notes updated</p>',
        }
    }
    response = graphql_client.execute(
        '''
            mutation updateTaskNotes($input: UpdateTaskInput!) {
                updateTaskNotes(input: $input) {
                  task {
                    id
                    implementationNotes
                  }
                }
            }
        ''',
        variables=variables,
    )

    data = dict(response['data']['updateTaskNotes']['task'])
    notes = data['implementationNotes']
    assert notes == '<p>task notes updated</p>'


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_organization_programs(graphql_client, graphql_organization, program):
    program_id = str(program.id)
    organization_id = str(graphql_organization.id)
    executed = graphql_client.execute(
        GET_ORGANIZATION_PROGRAMS, variables={'id': organization_id}
    )
    assert executed['data']['organizationPrograms'][0]['id'] == program_id


@pytest.mark.functional(permissions=['program.add_subtaskevidence'])
def test_add_subtask_evidence(graphql_client, subtask_1):
    variables = {
        'input': {
            'id': str(subtask_1.id),
            'timeZone': 'utc',
            'uploadedFiles': [
                {'fileName': 'evidence.txt', 'file': "b'RXZpZGVuY2UgZmlsZQ=='"}
            ],
        }
    }
    response = graphql_client.execute(ADD_SUBTASK_EVIDENCE, variables=variables)
    assert len(response['data']['addSubtaskEvidence']['documentIds']) != 0


@pytest.mark.functional(permissions=['program.add_subtaskevidence'])
def test_add_subtask_evidence_category_tags(graphql_client, subtask_1):
    variables = {
        'input': {
            'id': str(subtask_1.id),
            'timeZone': 'utc',
            'uploadedFiles': [
                {'fileName': 'evidence.txt', 'file': "b'RXZpZGVuY2UgZmlsZQ=='"}
            ],
        }
    }
    response = graphql_client.execute(ADD_SUBTASK_EVIDENCE, variables=variables)
    evidence_id = response['data']['addSubtaskEvidence']['documentIds'][0]
    category_tag_exists = TagEvidence.objects.filter(
        evidence__id=evidence_id, tag__name=subtask_1.task.category
    ).exists()
    assert category_tag_exists


@pytest.mark.functional(permissions=['program.add_subtaskevidence'])
def test_add_subtask_evidence_subtask_tags(graphql_client, subtask_1):
    variables = {
        'input': {
            'id': str(subtask_1.id),
            'timeZone': 'utc',
            'uploadedFiles': [
                {'fileName': 'evidence.txt', 'file': "b'RXZpZGVuY2UgZmlsXQ=='"}
            ],
        }
    }
    response = graphql_client.execute(ADD_SUBTASK_EVIDENCE, variables=variables)
    evidence_id = response['data']['addSubtaskEvidence']['documentIds'][0]
    subtask_tag_exists = TagEvidence.objects.filter(
        evidence__id=evidence_id, tag__name='Subtask Tag'
    ).exists()
    assert subtask_tag_exists
