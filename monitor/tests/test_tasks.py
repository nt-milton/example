import pytest

from monitor.tasks import validate_monitors
from monitor.tests.test_steampipe import create_aws_connection


@pytest.mark.functional
def test_validate_monitors(temp_query_runner):
    cnn = create_aws_connection()
    result = validate_monitors(cnn.organization.id)

    assert 'total' in result['errors']
    assert 'total' in result['no_apply']
