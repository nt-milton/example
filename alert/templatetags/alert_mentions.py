import re

from django import template
from django.utils.html import format_html

from user.models import User
from user.utils.name import get_capitalized_name

register = template.Library()


def find_occurrences(string, char):
    return [i for i, val in enumerate(string) if val == char]


@register.filter(name='highlight_mentions')
def highlight_mentions(content):
    formatted_content = content
    mention_starts_index = formatted_content.find('@(')

    if mention_starts_index < 0:
        return formatted_content

    pattern = re.compile(r"\@\((.*?)\)")
    mentions = pattern.findall(content)

    for mention in mentions:
        user = User.objects.get(email=mention)
        formatted_name = get_capitalized_name(user.first_name, user.last_name)
        formatted_content = formatted_content.replace(
            f'@({mention})',
            f'''
            <strong
                style="
                    margin-right: 4px;
                    padding-bottom: 2px;
                    padding-top: 2px;
                    font-size: 14px;
                    font-style: normal;
                    font-weight: 400;
                    line-height: 24px;
                    text-transform: none;
                    color: #3399FF;
                "
            >
                @{formatted_name}
            </strong>
            ''',
        )

    return format_html(formatted_content)
