from json import JSONDecodeError
from typing import List

from integration.integration_utils.mapping_utils import get_user_name_values
from integration.integration_utils.raw_objects_utils import replace_unsupported_unicode


def test_should_return_empty_name():
    result: List = get_user_name_values('')

    assert result[0] == ''
    assert result[1] == ''


def test_should_return_only_name():
    result: List = get_user_name_values('LaikaUser')

    assert result[0] == 'LaikaUser'
    assert result[1] == ''


def test_should_return_first_and_last_name():
    result: List = get_user_name_values('LaikaUser Test')

    assert result[0] == 'LaikaUser'
    assert result[1] == 'Test'


def test_with_multiple_last_names():
    result: List = get_user_name_values('LaikaUser Test name')

    assert result[0] == 'LaikaUser'
    assert result[1] == 'Test name'


def test_invalid_escape_and_unicode():
    json = {"robloxtypes": "\u0000jjghjhgjgh\jghjhgjghj\nhfghfgh"}  # noqa: W605
    try:
        parsed = replace_unsupported_unicode(json)
        assert json != parsed
    except JSONDecodeError as exc:
        assert False, f"{json} raised an exception {exc}"


def test_json_without_unsupported_values():
    json = {"key": "test", "other": {"laika": "test"}}
    try:
        parsed = replace_unsupported_unicode(json)
        assert json == parsed
    except JSONDecodeError as exc:
        assert False, f"{json} raised an exception {exc}"


def test_invalid_escape():
    json = {"robloxtypes": "A\T"}  # noqa: W605
    try:
        parsed = replace_unsupported_unicode(json)
        assert json == parsed
    except JSONDecodeError as exc:
        assert False, f"{json} raised an exception {exc}"
