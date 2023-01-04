import json
from datetime import datetime

import pytest

from alert.constants import ALERT_TYPES
from alert.models import Alert
from organization.tests import create_organization
from user.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_VIEWER
from user.models import (
    BACKGROUND_CHECK_STATUS_FLAGGED,
    BACKGROUND_CHECK_STATUS_NA,
    BACKGROUND_CHECK_STATUS_PASSED,
    BACKGROUND_CHECK_STATUS_PENDING,
    User,
)
from user.tests.factory import create_user

from ..models import LaikaObject, LaikaObjectType
from ..system_types import ACCOUNT, BACKGROUND_CHECK, USER, resolve_laika_object_type
from ..types import Types
from ..utils import (
    BACKGROUND_CHECK_TYPE,
    create_background_check_alerts,
    find_user_match_and_create_alerts_for_background_check,
    get_bgc_tray_keys,
)
from ..views import write_export_response
from .factory import (
    create_attribute,
    create_lo_with_connection_account,
    create_object_type,
)
from .mutations import ADD_OBJECT, BULK_DELETE_OBJECTS, GET_LAIKA_OBJECTS, UPDATE_OBJECT
from .queries import GET_LAIKA_OBJECT_BY_ID, GET_OBJECT_TYPES_PAGINATED, GET_OBJECTS

PENDING = 'pending'
LO_TYPE_A = 'value_a'
LO_TYPE_B = 'value_b'


@pytest.fixture
def organization():
    return create_organization(name='Laika', flags=[])


@pytest.fixture()
def lo_types_set_up(graphql_organization):
    LaikaObjectType.objects.create(
        organization=graphql_organization,
        display_name=LO_TYPE_A,
        display_index=1,
        type_name=LO_TYPE_A,
    )

    LaikaObjectType.objects.create(
        organization=graphql_organization,
        display_name=LO_TYPE_B,
        display_index=2,
        type_name=LO_TYPE_B,
    )


@pytest.mark.functional(permissions=['objects.add_laikaobject'])
def test_add_laika_object(graphql_client, graphql_organization):
    lo_type = resolve_laika_object_type(graphql_organization, USER)

    graphql_client.execute(
        ADD_OBJECT,
        variables={'input': {'laikaObjectType': lo_type.id, 'laikaObjectData': '{}'}},
    )
    lo = LaikaObject.objects.filter(object_type=lo_type).first()
    assert lo.is_manually_created


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_objects_query(graphql_client, graphql_organization):
    lo_type = resolve_laika_object_type(graphql_organization, USER)
    response = graphql_client.execute(
        GET_LAIKA_OBJECTS,
        variables={
            'query': json.dumps(dict(id=lo_type.type_name)),
            'pagination': {'pageSize': 50, 'page': 1},
        },
    )

    object_result = response['data']['objects'][0]
    assert object_result is not None
    elements = object_result['elements']
    assert len(elements) > 0


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_update_laika_object(graphql_client, graphql_organization):
    lo_type = resolve_laika_object_type(graphql_organization, USER)
    LaikaObject.objects.create(object_type=lo_type, data={})
    fields_to_update = {
        'Id': '99999',
        'First Name': 'First Name Updated',
        'Last Name': 'Last Name Updated',
        'Email': 'email+updated@heylaika.com',
        'Is Admin': False,
        'Title': 'Title Updated',
        'Roles': '',
        'Organization Name': 'Organization',
        'Mfa Enabled': True,
        'Mfa Enforced': True,
        'Source System': 'Source System Updated',
        'Connection Name': 'Connection Name Updated',
        'Groups': 'Groups Updated',
    }

    new_laika_object = LaikaObject.objects.filter(object_type=lo_type).first()
    graphql_client.execute(
        UPDATE_OBJECT,
        variables={
            'input': {
                'laikaObjectId': new_laika_object.id,
                'laikaObjectData': json.dumps(fields_to_update),
            }
        },
    )
    laika_object_updated = LaikaObject.objects.get(id=new_laika_object.id)
    for key, value in fields_to_update.items():
        assert value == laika_object_updated.data.get(key)


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_update_lo_background_check_link_to_people_existing_field(
    graphql_client, graphql_organization
):
    lo_type = resolve_laika_object_type(graphql_organization, BACKGROUND_CHECK)
    admin_user1 = create_user(
        graphql_organization,
        email='jhon1@heylaika.com',
        role=ROLE_ADMIN,
        first_name='leo',
        last_name='messi',
        background_check_passed_on=datetime.today(),
        background_check_status=BACKGROUND_CHECK_STATUS_PASSED,
    )
    LaikaObject.objects.create(
        object_type=lo_type,
        data={
            "Status": BACKGROUND_CHECK_STATUS_PASSED,
            'Link to People Table': {
                'id': admin_user1.id,
                'email': admin_user1.email,
                'lastName': admin_user1.last_name,
                'username': admin_user1.username,
                'firstName': admin_user1.first_name,
            },
        },
    )
    admin_user2 = create_user(
        graphql_organization,
        email='jhon2@heylaika.com',
        role=ROLE_ADMIN,
        first_name='leo',
        last_name='messi',
    )
    fields_to_update = {'Id': '88888', 'Link to People Table': admin_user2.email}

    new_laika_object = LaikaObject.objects.filter(object_type=lo_type).first()
    graphql_client.execute(
        UPDATE_OBJECT,
        variables={
            'input': {
                'laikaObjectId': new_laika_object.id,
                'laikaObjectData': json.dumps(fields_to_update),
            }
        },
    )
    user1 = User.objects.get(id=admin_user1.id)
    user2 = User.objects.get(id=admin_user2.id)
    assert user1.background_check_status == BACKGROUND_CHECK_STATUS_NA
    assert user1.background_check_passed_on is None
    assert user2.background_check_status == BACKGROUND_CHECK_STATUS_PENDING
    assert user2.background_check_passed_on is None


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_update_lo_background_check_link_to_people_field(
    graphql_client, graphql_organization
):
    lo_type = resolve_laika_object_type(graphql_organization, BACKGROUND_CHECK)
    LaikaObject.objects.create(
        object_type=lo_type, data={"Status": BACKGROUND_CHECK_STATUS_PENDING}
    )
    admin_user = create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='leo',
        last_name='messi',
    )
    fields_to_update = {'Id': '99999', 'Link to People Table': admin_user.email}

    new_laika_object = LaikaObject.objects.filter(object_type=lo_type).first()
    graphql_client.execute(
        UPDATE_OBJECT,
        variables={
            'input': {
                'laikaObjectId': new_laika_object.id,
                'laikaObjectData': json.dumps(fields_to_update),
            }
        },
    )
    user = User.objects.get(id=admin_user.id)
    assert user.background_check_status == BACKGROUND_CHECK_STATUS_PENDING
    assert user.background_check_passed_on is None


@pytest.mark.functional(permissions=['objects.delete_laikaobject'])
def test_bulk_delete_objects(graphql_client, graphql_organization):
    lo_type = resolve_laika_object_type(graphql_organization, USER)
    num_objects = 2
    laika_objects = [
        LaikaObject(object_type=lo_type, data={}) for _ in range(num_objects)
    ]
    LaikaObject.objects.bulk_create(laika_objects)
    new_objects_ids = list(LaikaObject.objects.all().values_list('id', flat=True))

    graphql_client.execute(
        BULK_DELETE_OBJECTS, variables={'input': {'laikaObjectIds': new_objects_ids}}
    )

    assert not LaikaObject.objects.exists()


@pytest.mark.functional(permissions=['objects.delete_laikaobject'])
def test_bulk_delete_lo_background_check_linked_with_user(
    graphql_client, graphql_organization
):
    lo_type = resolve_laika_object_type(graphql_organization, BACKGROUND_CHECK)
    num_objects = 1
    admin_user = create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='leo',
        last_name='messi',
        background_check_passed_on=datetime.today(),
        background_check_status=BACKGROUND_CHECK_STATUS_FLAGGED,
    )
    laika_objects = [
        LaikaObject(
            object_type=lo_type,
            data={
                "Link to People Table": {
                    "id": admin_user.id,
                    "email": admin_user.email,
                    "lastName": admin_user.last_name,
                    "username": admin_user.username,
                    "firstName": admin_user.first_name,
                }
            },
        )
        for _ in range(num_objects)
    ]
    LaikaObject.objects.bulk_create(laika_objects)
    new_objects_ids = list(LaikaObject.objects.all().values_list('id', flat=True))

    graphql_client.execute(
        BULK_DELETE_OBJECTS, variables={'input': {'laikaObjectIds': new_objects_ids}}
    )

    user = User.objects.get(id=admin_user.id)
    assert not LaikaObject.objects.exists()
    assert user.background_check_passed_on is None
    assert user.background_check_status == BACKGROUND_CHECK_STATUS_NA


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_resolve_objects_query_by_default(graphql_client, lo_types_set_up):
    params = {'query': '{"id": "default"}'}
    actual, *_ = graphql_client.execute(GET_OBJECTS, variables=params)['data'][
        'objects'
    ]
    assert actual.get('displayName') == LO_TYPE_A


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_resolve_objects_query_by_id(graphql_client, lo_types_set_up):
    params = {'query': '{"id": "value_b"}'}
    actual, *_ = graphql_client.execute(GET_OBJECTS, variables=params)['data'][
        'objects'
    ]

    assert actual.get('displayName') == LO_TYPE_B


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_resolve_objects_multiple_values(graphql_client, lo_types_set_up):
    params = {}
    response_objects = graphql_client.execute(GET_OBJECTS, variables=params)['data'][
        'objects'
    ]
    assert len(response_objects) == 2
    assert response_objects[0].get('displayName') == LO_TYPE_A
    assert response_objects[1].get('displayName') == LO_TYPE_B


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_object_by_id_query(graphql_client, graphql_organization):
    lo_type = resolve_laika_object_type(graphql_organization, USER)
    lo = LaikaObject.objects.create(object_type=lo_type, data={})

    response = graphql_client.execute(
        GET_LAIKA_OBJECT_BY_ID, variables={'id': lo.id, 'objectType': lo_type.type_name}
    )

    laika_object = response['data']['object']
    assert laika_object is not None
    assert laika_object['data'] is not None
    assert laika_object['id'] == '1'


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_objects_paginated_ordered_asc_query(graphql_client, graphql_organization):
    resolve_laika_object_type(graphql_organization, USER)
    resolve_laika_object_type(graphql_organization, ACCOUNT)
    response = graphql_client.execute(
        GET_OBJECT_TYPES_PAGINATED,
        variables={
            'orderBy': {'order': 'ascend', 'field': 'display_name'},
            'pagination': {'pageSize': 50, 'page': 1},
        },
    )
    objects_result = response['data']['objectsPaginated']['objects']
    assert len(objects_result) == 2
    assert objects_result[0]['displayName'] == 'Account'
    assert objects_result[1]['displayName'] == 'Integration User'


@pytest.mark.functional(permissions=['objects.view_laikaobject'])
def test_objects_paginated_with_search_criteria(graphql_client, graphql_organization):
    resolve_laika_object_type(graphql_organization, USER)
    resolve_laika_object_type(graphql_organization, ACCOUNT)
    response = graphql_client.execute(
        GET_OBJECT_TYPES_PAGINATED,
        variables={'pagination': {'pageSize': 50, 'page': 1}, 'searchCriteria': 'Int'},
    )
    objects_result = response['data']['objectsPaginated']['objects']
    assert len(objects_result) == 1
    assert objects_result[0]['displayName'] == 'Integration User'


@pytest.fixture()
def object_type(organization):
    return create_object_type(
        organization=organization,
        display_name='Change Request',
        type_name='change_request',
        color='accentRed',
        display_index=5,
    )


@pytest.mark.functional
def test_export_laika_objects(organization, object_type, caplog):
    invalid_description = (
        'This is text on the ticket. Invalid character => \x1f is gone'
    )
    valid_description = 'This is text on the ticket. Invalid character =>  is gone'
    create_attribute(
        object_type=object_type,
        name='Description',
        attribute_type=Types.TEXT.name,
        sort_index=1,
        metadata={"is_protected": True},
    )
    laika_object_type = LaikaObjectType.objects.get(
        organization=organization, id=object_type.id
    )
    bad_data = {
        "Key": "Ticket-123",
        "Url": "https://api.atlassian.com/ex/jira/1",
        "Epic": "Epic-123",
        "Ended": None,
        "Title": "Testing invalid characters on Excel - Export",
        "Status": "In Prod",
        "Project": "Export",
        "Started": "2021-12-08T14:10:14.614-0600",
        "Approver": None,
        "Assignee": "Otto",
        "Reporter": "James",
        "Issue Type": "Story",
        "Description": invalid_description,
        "Source System": "Jira",
        "Connection Name": "Jira Connection (1)",
        "Transitions History": {
            "data": [
                {
                    "date": "2021-09-20T15:53:08.003-0500",
                    "field": "created",
                    "author": "Otto",
                }
            ],
            "template": "jiraTransitionsHistory",
        },
    }
    LaikaObject.objects.create(object_type=object_type, data=bad_data)

    workbook = write_export_response(object_type.id, [laika_object_type])
    sheet = workbook.active
    assert sheet.cell(row=2, column=1).value == valid_description

    assert (
        "Error appending row data ['This is text on the ticket. "
        "Invalid character => \\x1f is gone'] for Laika object "
        "type Change Request in organization Laika"
        in caplog.text
    )


@pytest.mark.functional
def test_create_background_check_alerts(organization, object_type):
    laika_object, _ = create_lo_with_connection_account(organization, object_type)
    admin_user = create_user(
        organization, email='jhon@heylaika.com', role=ROLE_ADMIN, first_name='john'
    )
    super_admin = create_user(
        organization,
        email='jhon_super@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='john',
    )
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
    create_background_check_alerts(
        alert_related_object={'laika_object': laika_object},
        alert_related_model='objects.LaikaObjectAlert',
        alert_type=alert_type,
        organization_id=organization.id,
    )
    alert = Alert.objects.filter(type=alert_type)
    assert alert.count() == 2
    assert alert[0].receiver == admin_user
    assert alert[0].sender_name == 'Admin'
    assert alert[1].receiver == super_admin


@pytest.mark.functional
def test_find_user_single_match_and_create_alerts_for_background_check(organization):
    admin_user = create_user(
        organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='leo',
        last_name='messi',
    )
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO')
    find_user_match_and_create_alerts_for_background_check(
        first_name='leo', last_name='messi', organization_id=organization.id
    )
    alert = Alert.objects.filter(type=alert_type)
    assert alert.count() == 1
    assert alert[0].receiver == admin_user
    assert alert[0].sender_name == 'Admin'


@pytest.mark.functional
def test_find_user_single_match_by_email_create_alerts_for_background_check(
    organization,
):
    admin_user = create_user(
        organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='leo',
        last_name='messi',
    )
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO')
    find_user_match_and_create_alerts_for_background_check(
        first_name='xxxx',
        last_name='yyyy',
        email='jhon@heylaika.com',
        organization_id=organization.id,
    )
    alert = Alert.objects.filter(type=alert_type)
    assert alert.count() == 1
    assert alert[0].receiver == admin_user
    assert alert[0].sender_name == 'Admin'


@pytest.mark.functional
def test_find_user_multiple_match_and_create_alerts_for_background_check(organization):
    admin_user_1 = create_user(
        organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='leo',
        last_name='messi',
    )
    _ = create_user(
        organization,
        email='jhon2@heylaika.com',
        role=ROLE_VIEWER,
        first_name='LEO',
        last_name='MESSI',
    )
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_MULTIPLE_MATCH_USER_TO_LO')
    find_user_match_and_create_alerts_for_background_check(
        first_name='leo', last_name='messi', organization_id=organization.id
    )
    alert = Alert.objects.filter(type=alert_type)
    assert alert.count() == 1
    assert alert[0].receiver == admin_user_1
    assert alert[0].sender_name == 'Admin'


@pytest.mark.functional
def test_get_bgc_tray_keys():
    type_key, description_key, label_key = get_bgc_tray_keys()
    assert type_key == BACKGROUND_CHECK_TYPE
    assert description_key == BACKGROUND_CHECK_TYPE
    assert label_key == BACKGROUND_CHECK_TYPE
