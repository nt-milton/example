import pytest

from monitor.sqlutils import add_criteria


@pytest.mark.parametrize(
    'query, expected',
    [
        ('SELECT * FROM test_table', 'SELECT * FROM test_table WHERE test_table.id=1'),
        ('SELECT * FROM test_table;', 'SELECT * FROM test_table WHERE test_table.id=1'),
        (
            'SELECT * FROM test_table LIMIT 20',
            'SELECT * FROM test_table WHERE test_table.id=1 LIMIT 20',
        ),
        (
            'SELECT * FROM test_table where 2>1 LIMIT 20',
            'SELECT * FROM test_table where 2>1 AND test_table.id=1 LIMIT 20',
        ),
        (
            'SELECT id, count(*) FROM test_table GROUP by id LIMIT 20',
            'SELECT id, count(*) FROM test_table '
            'WHERE test_table.id=1 GROUP by id LIMIT 20',
        ),
        (
            'SELECT id, count(*) FROM test_table WHERE 2>1 GROUP by id',
            'SELECT id, count(*) FROM test_table WHERE 2>1 '
            'AND test_table.id=1 GROUP by id',
        ),
    ],
)
def test_add_criteria(query, expected):
    criteria = 'test_table.id=1'
    result_query = add_criteria(query, criteria)
    assert result_query == expected


def test_add_empty_criteria():
    query = 'SELECT * FROM test_table'
    result_query = add_criteria(query, '')
    assert result_query == query
