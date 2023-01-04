from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import ControlFamilyBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import CONTROL_FAMILY_REQUIRED_FIELDS, NAME
from blueprint.models import ControlFamilyBlueprint
from blueprint.tests.test_commons import get_airtable_sync_class
from user.models import User


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[{'id': '1234asd', 'fields': {NAME: 'Const Tam', 'Acronym': 'CT'}}],
)
def test_airtable_init_update_control_family_unit(
    execute_airtable_request_mock, graphql_user
):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert not blueprint_base.init_update(None)
    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(
        graphql_user, CONTROL_FAMILY_REQUIRED_FIELDS
    )
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return ControlFamilyBlueprintAdmin(
        model=ControlFamilyBlueprint, admin_site=AdminSite()
    )
