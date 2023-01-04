from monitor.timeline import Interval
from monitor.views import write_csv, write_xls

QUERY = 'select * from users'
DATE = '2021-06-14T23:43:39.523870'

MONITOR_JSON = {
    'name': 'Test',
    'description': 'Lorem ipsum',
    'status': 'active',
    'healthCondition': 'return_results',
    'frequency': 'daily',
    'urgency': 'low',
    'query': QUERY,
    'controlReferences': "Control 1\r\nControl 2",
}

TAGS = [
    {'id': '3346', 'name': 'Dos', '__typename': 'TagType'},
    {'id': '3344', 'name': 'Tres', '__typename': 'TagType'},
]

TIMELINE = [Interval(DATE, DATE, 'healthy', '', '')]

EXPECTED_ROW = (
    'Test,Lorem ipsum,"\'Dos\', \'Tres\'",low,"\'Control 1\', \'Control 2\'"'
    f',{DATE},healthy,Healthy if monitor returns results,{QUERY}\r\n'
)

EXPECTED = (
    'Monitor Name,Description,Tags,Urgency,Control References,'
    'Run Timestamp,Health,Healthy If,Query\r\n'
    f'{EXPECTED_ROW}'.encode()
)


def test_write_csv():
    response = write_csv(MONITOR_JSON, TIMELINE, TAGS)
    assert response.getvalue() == EXPECTED


def test_write_xls():
    response = write_xls(MONITOR_JSON, TIMELINE, TAGS)
    assert len(response.getvalue()) > 0
    assert response.status_code == 200
