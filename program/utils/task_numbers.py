from django.db import models


def create_task_initials(task):
    task_initials = ''
    category_tokens = task.category.replace('&', '').replace('-', ' ').split()

    if len(category_tokens) > 1:
        for token in category_tokens:
            task_initials += token[0].upper()
        task_initials = task_initials[0:2]
    else:
        task_initials = task.category[0:2].upper()
    return task_initials


def populate_task_numbers(Task):
    for task in Task.objects.all():
        customer_identifier = create_task_initials(task)

        last_number = 1
        provisional_identifier = customer_identifier + str(last_number)

        while len(
            Task.objects.filter(
                program=task.program, customer_identifier=provisional_identifier
            )
        ):
            last_number += 1
            provisional_identifier = customer_identifier + str(last_number)

        task.number = last_number
        task.customer_identifier = customer_identifier + str(task.number)
        task.save()


def populate_subtask_numbers(SubTask):
    for subtask in SubTask.objects.all():
        last_number = SubTask.objects.filter(
            group=subtask.group, task=subtask.task
        ).aggregate(largest=models.Max('number'))['largest']

        subtask.number = last_number + 1
        subtask.customer_identifier = (
            subtask.task.customer_identifier
            + '-'
            + subtask.group[0].upper()
            + str(subtask.number)
        )
        subtask.save()
