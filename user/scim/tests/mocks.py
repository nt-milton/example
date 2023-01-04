SCIM_EMAIL = 'test-scim@laiak-scim.com'
SCHEMA_MOCK = ['urn:ietf:params:scim:schemas:core:2.0:User']
SCIM_NAME = 'Test User'
MOCKED_USERNAME = '123456'

CREATE_USER_REQUEST = {
    'schemas': SCHEMA_MOCK,
    'userName': SCIM_EMAIL,
    'name': {'givenName': 'Test', 'familyName': 'User'},
    'emails': [{'primary': True, 'value': SCIM_EMAIL, 'type': 'work'}],
    'displayName': SCIM_NAME,
    'locale': 'en-US',
    'externalId': 'abc123456789',
    'groups': ['LaikaAdmin'],
    'active': True,
}

CREATE_USER_BAD_REQUEST = {
    'schemas': SCHEMA_MOCK,
    'userName': SCIM_EMAIL,
    'name': {'familyName': 'User'},
    'emails': [{'primary': True, 'value': SCIM_EMAIL, 'type': 'work'}],
    'displayName': SCIM_NAME,
    'locale': 'en-US',
    'externalId': 'abc123456789',
    'groups': ['LaikaAdmin'],
    'active': True,
}

CREATE_USER_REQUEST_BAD_EMAIL = {
    'schemas': SCHEMA_MOCK,
    'userName': SCIM_EMAIL,
    'name': {'givenName': 'Test', 'familyName': 'User'},
    'emails': [{'primary': True, 'value': 'not an email', 'type': 'work'}],
    'displayName': SCIM_NAME,
    'locale': 'en-US',
    'externalId': 'abc123456789',
    'groups': ['LaikaAdmin'],
    'active': True,
}

CREATE_USER_REQUEST_NO_GROUPS = {
    'schemas': SCHEMA_MOCK,
    'userName': SCIM_EMAIL,
    'name': {'givenName': 'Test', 'familyName': 'User'},
    'emails': [{'primary': True, 'value': SCIM_EMAIL, 'type': 'work'}],
    'displayName': SCIM_NAME,
    'locale': 'en-US',
    'externalId': 'abc123456789',
    'groups': [],
    'active': True,
}

PATCH_USER_REQUEST = {
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
    "operations": [{"op": "replace", "value": {"active": False}}],
}
