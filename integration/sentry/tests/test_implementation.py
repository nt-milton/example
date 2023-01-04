from integration.sentry.implementation import _reach_stop


def test_reach_stop_found():
    assert _reach_stop([{'eventID': '1'}, {'eventID': '2'}], '1')


def test_reach_stop_not_found():
    assert not _reach_stop([{'eventID': '1'}], '2')


def test_reach_stop_without_stop():
    assert not _reach_stop([{'eventID': '1'}], None)
