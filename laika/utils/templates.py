from django.template.loader import render_to_string

from laika.utils.dates import now_date


def render_template(template, context, time_zone=None):
    if time_zone:
        time = now_date(time_zone, 'Exported on %m/%d/%Y at %H:%M:%S')
        context.update({'time': time})

    return render_to_string(template, context)
