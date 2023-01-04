from datetime import date

from django.db.models import QuerySet

from dashboard.models import (
    DefaultTask,
    Task,
    TaskSubTypes,
    TaskTypes,
    UserTask,
    UserTaskStatus,
)
from laika.aws.ses import send_email
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from monitor.models import MonitorInstanceStatus, MonitorUrgency, OrganizationMonitor
from user.models import User

FLAGGED_URGENT_MONITOR_SUBJECT = 'An urgent compliance monitor has detected a violation'
MAX_EMAILS = 50


def reconcile_action_items(organization_monitor: OrganizationMonitor) -> None:
    urgency = organization_monitor.monitor_urgency
    status = organization_monitor.status
    active = organization_monitor.active
    if urgency == MonitorUrgency.LOW or not active:
        delete_action_items(organization_monitor)
        return
    if (
        status == MonitorInstanceStatus.CONNECTION_ERROR
        or status == MonitorInstanceStatus.NO_DATA_DETECTED
    ):
        return
    if status == MonitorInstanceStatus.HEALTHY:
        complete_healthy_action_items(organization_monitor)
        return
    watchers = find_watchers(organization_monitor)
    delete_user_tasks_without_watchers(organization_monitor, watchers)
    create_monitor_user_task(organization_monitor, watchers)


def delete_user_tasks_without_watchers(
    organization_monitor: OrganizationMonitor, watchers: list[User]
) -> None:
    UserTask.objects.filter(organization_monitor=organization_monitor).exclude(
        assignee__in=watchers
    ).delete()


def find_watchers(organization_monitor: OrganizationMonitor) -> list[User]:
    return User.objects.filter(watchers__organization_monitor=organization_monitor)


def complete_healthy_action_items(organization_monitor: OrganizationMonitor) -> None:
    UserTask.objects.filter(organization_monitor=organization_monitor).update(
        status=UserTaskStatus.COMPLETED
    )


def delete_action_items(organization_monitor: OrganizationMonitor) -> None:
    UserTask.objects.filter(organization_monitor=organization_monitor).delete()


def create_monitor_user_task(
    organization_monitor: OrganizationMonitor, watchers: list[User]
) -> None:
    urgency = organization_monitor.monitor_urgency
    task = create_or_update_monitor_task(organization_monitor.id)
    completed_action_items = find_completed_action_items(organization_monitor)
    is_urgent = urgency == MonitorUrgency.URGENT
    urgency_emails = [ut.assignee.email for ut in completed_action_items if is_urgent]
    completed_action_items.update(status=UserTaskStatus.NOT_STARTED)
    for user in watchers:
        created = update_or_create_user_task(organization_monitor, task, user)
        if created and is_urgent:
            urgency_emails.append(user.email)
    send_urgent_monitor_email(organization_monitor, urgency_emails)


def update_or_create_user_task(
    organization_monitor: OrganizationMonitor, task: Task, user: User
) -> bool:
    description = f'Flagged Monitor: {organization_monitor.monitor.name}'
    user_task, created = UserTask.objects.update_or_create(
        task=task,
        assignee=user,
        organization_monitor=organization_monitor,
        organization=user.organization,
        defaults=dict(
            status=UserTaskStatus.NOT_STARTED,
            description=description,
            reference_url=f'/{organization_monitor.monitor.id}',
            due_date=date.today(),
        ),
    )
    return created


def find_completed_action_items(
    organization_monitor: OrganizationMonitor,
) -> QuerySet[UserTask]:
    return UserTask.objects.filter(
        organization_monitor=organization_monitor, status=UserTaskStatus.COMPLETED
    )


def create_or_update_monitor_task(id) -> Task:
    task, *_ = Task.objects.get_or_create(
        name=f'{DefaultTask.MONITOR_TASK} {id}',
        task_type=TaskTypes.MONITOR_TASK,
        task_subtype=TaskSubTypes.MONITOR,
        defaults=dict(description='Monitor task'),
    )
    return task


def send_urgent_monitor_email(
    organization_monitor: OrganizationMonitor, emails: list[str]
):
    if not emails:
        return
    template_context = _get_template_context(organization_monitor)
    chunks = [emails[n : n + MAX_EMAILS] for n in range(0, len(emails), MAX_EMAILS)]
    for chunk in chunks:
        send_email(
            subject=FLAGGED_URGENT_MONITOR_SUBJECT,
            from_email=NO_REPLY_EMAIL,
            to=chunk,
            template='urgent_monitor_flagged.html',
            template_context=template_context,
        )


def _get_template_context(organization_monitor: OrganizationMonitor):
    return {
        'monitor_name': organization_monitor.monitor.name,
        'monitor_id': organization_monitor.id,
        'monitor_url': (
            f"{DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')}"
            f"/monitors/{organization_monitor.monitor.id}"
        ),
        'web_url': DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT'),
    }
