from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import EvidenceMetadataBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    ATTACHMENT,
    DESCRIPTION,
    EVIDENCE_METADATA_REQUIRED_FIELDS,
    LAST_MODIFIED,
    NAME,
    REFERENCE_ID,
)
from blueprint.models.evidence_metadata import EvidenceMetadataBlueprint
from blueprint.tests.test_commons import RECORD_ID_MOCK, get_airtable_sync_class
from user.models import User

FAKE_EVIDENCE_FILE_NAME = 'Fake Evidence Metadata.pdf'
FAKE_EVIDENCE_REFERENCE_ID = 'EVIDENCE-AC-S-001'
FAKE_ACTION_ITEM_REFERENCE_ID = 'AC-S-001'
EVIDENCE_METADATA_AIRTABLE_MOCK = {
    'id': RECORD_ID_MOCK,
    'fields': {
        NAME: 'Evidence name',
        DESCRIPTION: 'Evidence description',
        REFERENCE_ID: FAKE_ACTION_ITEM_REFERENCE_ID,
        ATTACHMENT: [
            {
                'id': 'att96aAQNh5t7j5nu',
                'url': 'http://fakeurl.com/somelongfile',
                'filename': FAKE_EVIDENCE_FILE_NAME,
                'size': 841852,
                'type': 'application/pdf',
                'thumbnails': {
                    'small': {
                        'url': 'http://fakeurl.com/somelongfile',
                        'width': 64,
                        'height': 36,
                    },
                    'large': {
                        'url': 'http://fakeurl.com/somelongfile',
                        'width': 512,
                        'height': 288,
                    },
                },
            }
        ],
        LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
    },
}


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[EVIDENCE_METADATA_AIRTABLE_MOCK],
)
def test_airtable_sync_create_evidence_metadata_blueprint(
    execute_airtable_request_mock, graphql_user
):
    expected_status_detail = [
        'Record created successfully: Evidence name',
        'Records deleted: []',
    ]
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert EvidenceMetadataBlueprint.objects.count() == 1
    assert EvidenceMetadataBlueprint.objects.get(
        reference_id=FAKE_ACTION_ITEM_REFERENCE_ID
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


def get_blueprint_admin_mock():
    return EvidenceMetadataBlueprintAdmin(
        model=EvidenceMetadataBlueprint, admin_site=AdminSite()
    )
