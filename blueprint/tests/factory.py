import random
import string
from datetime import datetime

from blueprint.models.action_item import ActionItemBlueprint
from blueprint.models.control import ControlBlueprint
from blueprint.models.tag import TagBlueprint


def generate_random_string(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters, k=length))


def create_control_blueprint(**kwargs) -> ControlBlueprint:
    return ControlBlueprint.objects.create(
        **kwargs,
        updated_at=datetime.strptime(
            '2022-03-01T23:19:58.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
        ),
    )


def create_action_item_blueprint():
    random_string = generate_random_string(3)
    return ActionItemBlueprint.objects.create(
        airtable_record_id='whathever_id_you_want',
        name=f'Action Item {random_string}',
        reference_id=f'AC-S-{random_string}',
        description='Description for action item',
        suggested_owner='Technical',
        display_id=random.randint(1, 9),
        updated_at=datetime.strptime(
            '2022-03-01T23:19:58.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
        ),
    )


def create_tag_blueprint(**kwargs):
    return TagBlueprint.objects.create(
        **kwargs,
        updated_at=datetime.strptime(
            '2022-03-01T23:19:58.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
        ),
    )
