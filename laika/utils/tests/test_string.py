import pytest

from laika.utils.strings import right_replace_char_from_string


@pytest.mark.parametrize(
    "current_str, old, new, occurrence, result",
    [
        ('Monday, Tuesday, Wednesday', ',', ' and', 1, 'Monday, Tuesday and Wednesday'),
        (
            'Remove last occurrence of a BAD word. This is a last BAD word.',
            'BAD',
            'GOOD',
            2,
            'Remove last occurrence of a GOOD word. This is a last GOOD word.',
        ),
        (
            'Remove last occurrence of a BAD word. This is a last BAD word.',
            'BAD',
            'GOOD',
            1,
            'Remove last occurrence of a BAD word. This is a last GOOD word.',
        ),
    ],
)
def test_attachment_query_exist(current_str, old, new, occurrence, result):
    assert right_replace_char_from_string(current_str, old, new, occurrence) == result
