from alert.models import Alert
from program.models import (
    ArchivedProgram,
    ArchivedSubtask,
    ArchivedTask,
    ArchivedUser,
    Program,
    Task,
)


def create_program(organization, name, description):
    program = Program(organization=organization, name=name, description=description)
    program.save(no_cache=True)
    return program


def create_task(
    organization, program=None, name='Task 1', description='Task description 1'
):
    if not program:
        program = create_program(
            organization, name='Program Test 1', description='Test Program 1'
        )

    return Task.objects.create(name=name, description=description, program=program)


def create_archived_program(organization, program):
    return ArchivedProgram.objects.create(data=program, organization=organization)


def create_archived_task(program, task):
    return ArchivedTask.objects.create(
        data=task, program=program, organization=program.organization
    )


def create_archived_subtask(task, subtask):
    return ArchivedSubtask.objects.create(
        data=subtask,
        task=task,
    )


def create_alert(receiver, sender, alert_type):
    return Alert.objects.create(receiver=receiver, sender=sender, type=alert_type)


def create_archived_user(first_name, last_name, email):
    return ArchivedUser.objects.create(
        first_name=first_name, last_name=last_name, email=email
    )


def associate_certification_sections_to_subtask(subtask, certification_sections):
    subtask.certification_sections.set(certification_sections)


def associate_task_to_program(program, tasks):
    program.tasks.set(tasks)
