from datetime import datetime, timezone

from django import template
from django.utils.html import format_html

from action_item.constants import (
    TYPE_ACCESS_REVIEW,
    TYPE_CONTROL,
    TYPE_POLICY,
    TYPE_QUICK_START,
)
from dashboard.models import TaskTypes

register = template.Library()


def due_date(content):
    if not content:
        return format_html("<span style='color: #232735;'>due</span>")

    delta_days = (datetime.now(timezone.utc) - content).days
    days_str = "day" if abs(delta_days) == 1 else "days"

    if delta_days > 0:
        return f"<span style='color: #D00001'>{delta_days} {days_str} overdue</span>"
    elif delta_days == 0:
        return "<span style='color: #D00001'>due today</span>"
    elif delta_days < 0:
        return (
            f"<span style='color: #232735;'>due in {abs(delta_days)} {days_str}</span>"
        )


@register.simple_tag
def action_items_render(action_item):
    src = 'https://laika-static-documents.s3.amazonaws.com/Email+Templates/'
    message = None
    metadata = getattr(action_item, 'metadata', None)
    action_type = getattr(action_item, 'type', None)
    if metadata:
        if metadata['type'] == TYPE_CONTROL:
            src += 'control-icon.png'
            message = (
                'You have an action item '
                f'{due_date(action_item.due_date)} in <strong>'
                f'{action_item.controls.first().name }</strong>'
            )
        elif metadata['type'] == TYPE_QUICK_START:
            src += 'quick-start-icon.png'
            message = (
                'You have an action item '
                f'{due_date(action_item.due_date)} in <strong>'
                f'{action_item.description}</strong>'
            )
        elif metadata['type'] == TYPE_POLICY:
            src += 'policy-icon.png'
            message = (
                'You have an action item '
                f'{due_date(action_item.due_date)} in <strong>'
                f'{action_item.name}</strong>'
            )
        elif metadata['type'] == TYPE_ACCESS_REVIEW:
            src += 'wifi-tethering.png'
            message = (
                'You have an action item '
                f'{due_date(action_item.due_date)} in <strong>'
                f'{action_item.name}</strong>'
            )
    elif action_type:
        if action_type == TaskTypes.MONITOR_TASK.value:
            src += 'wifi-tethering.png'
            message = (
                '<span style="font-family: Roboto, Rubik, Arial, '
                'Helvetica, Verdana, sans-serif;font-style: normal; '
                'font-size: 14px;line-height: 24px;'
                'color: #232735;font-weight: bold;"> '
                f'{action_item.description}</span>'
            )
        elif action_type == 'playbook_task':
            src += 'local_library.png'
            message = (
                f'{action_item.group.capitalize()} subtask in '
                f'<strong>{action_item.description} </strong>'
            )
    else:
        src += 'local_library.png'

    html_icon = (
        "<td style='border-top: 1px solid #DDDAE0;padding: 16px 15px;"
        "width: 20px;vertical-align: top;'> "
        "<img style='width: 20px;height: 20px;"
        "vertical-align: middle;'"
        "alt='Laika action item icon' src={}></td>"
    ).format(src)

    html_message = (
        "<td style='border-top: 1px solid #DDDAE0;"
        "padding: 16px 15px 16px 0px; vertical-align: top; "
        "font-family: Roboto, Rubik, Arial, Helvetica, Verdana, "
        "sans-serif;font-style: normal;font-weight: normal; "
        "font-size: 14px;line-height: 24px;color: #232735;'>"
        "{}</td>".format(message)
    )

    return format_html(f'{html_icon}{html_message}')
