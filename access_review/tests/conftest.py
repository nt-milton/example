from pathlib import Path

import pytest
from django.core.files import File


@pytest.fixture
def access_review_file():
    path = Path(__file__).parent / 'mock_files/attachment.txt'
    with open(path, 'rb') as file:
        yield File(file, name='attachment.txt')
