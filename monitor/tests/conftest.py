from unittest.mock import patch

import pytest

from monitor.result import Result


@pytest.fixture
def steampipe_folder(tmpdir):
    tmpdir.mkdir('.steampipe').mkdir('config')
    with patch('monitor.steampipe.Path') as mock:
        mock.home.return_value = str(tmpdir)
        yield


@pytest.fixture
def temp_query_runner(steampipe_folder):
    with patch('monitor.steampipe.run_query') as mock:
        mock.side_effect = lambda x: Result(columns=[x], data=[])
        yield
