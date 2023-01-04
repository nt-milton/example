from search.utils import get_result_content


def test_get_result_context_none_value():
    empty = ''
    assert empty == get_result_content(empty, None, 'un')


def test_get_result_context_with_value():
    description = 'description untitled'
    assert description == get_result_content(description, '', 'un')
