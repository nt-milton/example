from integration.shortcut.rest_client import get_all_tickets
from laika.tests import mock_responses


def test_get_tickets_max_records():
    with mock_responses(
        responses=[' {"error": "maximum-results-exceeded"}'], status_code=400
    ):
        tickets = get_all_tickets('key', 'p_id', None)
        assert list(tickets) == []
