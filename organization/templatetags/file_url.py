from django import template

register = template.Library()


@register.filter(name='file_url')
def file_url(file):
    return file.url if file else None
