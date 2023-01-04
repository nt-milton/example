import pytest as pytest


@pytest.fixture
def mock_renew_token():
    from unittest.mock import patch

    with patch('integration.token._token_requires_renew') as mock_renew_token:
        mock_renew_token.return_value = False
        yield
