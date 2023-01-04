import html
import re

from django.template import Context, Template

from laika import settings
from laika.constants import (
    COMPANY_LOGO_PLACEHOLDER,
    COMPANY_NAME_PLACEHOLDER,
    SUFFIX_LOGO_PLACEHOLDER,
)

from .regex import SPECIAL_CHAR


def __get_logo_url(s3_obj):
    return f'https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_obj.key}'


def organization_placeholders(organization):
    org_placeholders = {COMPANY_NAME_PLACEHOLDER: organization.name}
    if organization.logo:
        org_placeholders[COMPANY_LOGO_PLACEHOLDER] = organization.logo.file
    return org_placeholders


def replace_html_template_text(html_text, placeholders):
    def placeholder(key, value):
        if key.endswith(SUFFIX_LOGO_PLACEHOLDER):
            return (
                f'<img src="{__get_logo_url(value.obj)}" '
                'alt="Company Logo" '
                'width="auto" height="100" />'
            )
        else:
            return value

    template = Template(html_text)
    context = {k: placeholder(k, v) for (k, v) in placeholders.items()}
    placeholder_context = Context(context)
    return html.unescape(template.render(placeholder_context))


def replace_special_char(text=''):
    return re.sub(SPECIAL_CHAR, '_', text)
