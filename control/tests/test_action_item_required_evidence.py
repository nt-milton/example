import pytest

from action_item.models import ActionItem
from control.mutations import clean_required_evidence


@pytest.mark.parametrize(
    'input_value,expected',
    [
        (ActionItem(metadata={'requiredEvidence': True}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 'true'}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 'True'}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 't'}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 'T'}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 1}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': '1'}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 'yes'}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 'Yes'}), 'Yes'),
        (ActionItem(metadata={'requiredEvidence': 'no'}), 'No'),
        (ActionItem(metadata={'requiredEvidence': 'No'}), 'No'),
        (ActionItem(metadata={'requiredEvidence': 'Hello'}), 'No'),
        (ActionItem(metadata={'requiredEvidence': ''}), 'No'),
        (ActionItem(), 'No'),
    ],
)
def test_clean_required_evidence_yes(input_value, expected):
    """
    Test the clean value of the required evidence input
    """
    clean_required_evidence(input_value)
    assert input_value.metadata['requiredEvidence'] == expected
