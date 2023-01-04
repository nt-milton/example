from django import template

register = template.Library()


@register.filter(name='humanize_date')
def humanize_date(value):
    '''
    built to use with timesince template filter
    e.g.
    created_at|timesince => 2 hours, 35 minutes ago
    created_at|timesince|humanize_date => 2 hours ago
    '''
    return value.split(',')[0]
