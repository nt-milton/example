from monitor.exclusion import add_exclusion_criteria
from monitor.models import MonitorExclusion


def test_add_exclusion_criteria_empty_exclusions():
    query = "select * from test_table"
    result_query = add_exclusion_criteria([], query, "test_table.id")
    assert result_query == query


def test_add_exclusion_criteria_add_where():
    query = "select * from test_table"
    result_query = add_exclusion_criteria(
        [MonitorExclusion(value='12', key='value')], query, "test_table.id"
    )
    assert (
        result_query.lower()
        == "select * from test_table where test_table.id not in ('12')".lower()
    )


def test_add_exclusion_criteria_add_and():
    query = 'select * from test_table where active="true"'
    result_query = add_exclusion_criteria(
        [MonitorExclusion(value='12', key='value')], query, "test_table.id"
    )
    assert (
        result_query.lower()
        == "select * from test_table where active=\"true\" "
        "and test_table.id not in ('12')".lower()
    )


def test_add_exclusion_criteria_many_exclusions():
    query = 'select * from test_table where active="true"'
    exclusions = [
        MonitorExclusion(value='12', key='value'),
        MonitorExclusion(value='13', key='value'),
        MonitorExclusion(value='14', key='value'),
    ]
    result_query = add_exclusion_criteria(exclusions, query, "test_table.id")
    assert (
        result_query.lower()
        == (
            "select * from test_table where active=\"true\" "
            "and test_table.id not in ('12', '13', '14')"
        ).lower()
    )
