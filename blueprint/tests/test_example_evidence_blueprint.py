from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import EvidenceMetadataBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    ATTACHMENT,
    CONTENT_STATUS,
    DESCRIPTION,
    EVIDENCE_METADATA_REQUIRED_FIELDS,
    LAST_MODIFIED,
    NAME,
    REFERENCE_ID,
)
from blueprint.models import EvidenceMetadataBlueprint
from blueprint.tests.test_commons import RECORD_ID_MOCK, get_airtable_sync_class
from user.models import User

LAST_MODIFIED_VALUE = '2022-03-01T23:19:58.000Z'
REFERENCE_ID_001 = '00-S-022'
REFERENCE_ID_002 = 'AC-R-009'
EVIDENCE_METADATA001_AIRTABLE_MOCK = {
    'id': RECORD_ID_MOCK,
    'fields': {
        NAME: 'Evidence Metadata 001',
        REFERENCE_ID: REFERENCE_ID_001,
        CONTENT_STATUS: 'Approval',
        DESCRIPTION: 'description 001',
        ATTACHMENT: '',
        LAST_MODIFIED: LAST_MODIFIED_VALUE,
    },
}

EVIDENCE_METADATA002_AIRTABLE_MOCK = {
    'id': RECORD_ID_MOCK,
    'fields': {
        NAME: 'Evidence Metadata 002',
        REFERENCE_ID: REFERENCE_ID_002,
        CONTENT_STATUS: 'Approval',
        DESCRIPTION: 'description 002',
        ATTACHMENT: '',
        LAST_MODIFIED: LAST_MODIFIED_VALUE,
    },
}


def get_blueprint_admin_mock():
    return EvidenceMetadataBlueprintAdmin(
        model=EvidenceMetadataBlueprint, admin_site=AdminSite()
    )


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(
        graphql_user, EVIDENCE_METADATA_REQUIRED_FIELDS
    )
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        EVIDENCE_METADATA001_AIRTABLE_MOCK,
        EVIDENCE_METADATA002_AIRTABLE_MOCK,
    ],
)
def test_airtable_sync_update_action_item_blueprint(
    execute_airtable_request_mock, graphql_user
):
    expected_status_detail = [
        'Record created successfully: Evidence Metadata 001',
        'Record created successfully: Evidence Metadata 002',
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert EvidenceMetadataBlueprint.objects.count() == 2
    assert EvidenceMetadataBlueprint.objects.get(reference_id=REFERENCE_ID_001)
    assert EvidenceMetadataBlueprint.objects.get(reference_id=REFERENCE_ID_002)


@pytest.mark.django_db
def test_get_default_fields(graphql_user):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    fields = EVIDENCE_METADATA001_AIRTABLE_MOCK.get('fields')
    default_fields = blueprint_base.get_default_fields(fields, {})
    assert default_fields.get('name') == 'Evidence Metadata 001'
    assert default_fields.get('description') == 'description 001'
