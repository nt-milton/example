from django import template

register = template.Library()


@register.filter(name='replace_eol_to_line_break')
def replace_eol_to_line_break(value):
    return value.replace("\n", "<br />")
