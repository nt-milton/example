import re
import secrets
import string

from .regex import REGEX_CAMEL_CASE, REGEX_UPPER_CASE


def random_string(length=20):
    '''Generate a random string of fixed length'''
    letters = string.ascii_letters
    return ''.join(secrets.choice(letters) for _ in range(length))  # nosec


def get_temporary_random_password(length=10):
    random_source = string.ascii_letters + string.digits + string.punctuation
    password_requirements = (
        secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.digits)
        + secrets.choice(string.punctuation)
    )

    random_pass = [secrets.choice(random_source) for _ in range(length)]
    return password_requirements + ''.join(random_pass)


def get_random_otp(length=6):
    random_pass = [secrets.choice(string.digits) for _ in range(length)]
    return ''.join(random_pass)


def camel_to_snake(name):
    name = re.sub(REGEX_UPPER_CASE, r'\1_\2', name)
    return re.sub(REGEX_CAMEL_CASE, r'\1_\2', name).lower()


def remove_prefix(str, prefix):
    if str.startswith(prefix):
        return str.replace(prefix, '', 1)
    return str


def find_between(text, first, last):
    try:
        start = text.index(first) + len(first)
        end = text.index(last, start)
        return text[start:end]
    except ValueError:
        return ""


def right_replace_char_from_string(
    current_str: str, old: str, new: str, occurrence: int
) -> str:
    '''
    Replace character from a string starting from the right
    e.g.
    input: ('Monday, Tuesday, Wednesday', ',', 'and', 1)
    output: Monday, Tuesday and Wednesday
    '''
    li = current_str.rsplit(old, occurrence)
    return new.join(li)
