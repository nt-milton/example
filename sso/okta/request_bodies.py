import datetime
import math

from laika.settings import ENVIRONMENT
from sso.constants import BASE_CERTIFICATE_ID, IDP_INACTIVE, OKTA_DUMMY_URL, OKTA_GROUPS

CUSTOM = '#custom'
FIRST_NAME = 'First Name'
LAST_NAME = 'Last Name'
APP_USER_EMAIL = 'appuser.email'
APP_USER_ROLE = 'appuser.role'

MAX_ORG_NAME_LENGTH = 60


def generate_request_body(organization_name, provider):
    ts = math.trunc(datetime.datetime.now().timestamp())
    short_organization_name = f'{organization_name[0:MAX_ORG_NAME_LENGTH]}'
    return {
        'type': 'SAML2',
        'name': f'{short_organization_name} {provider} SAML {ts}',
        'status': IDP_INACTIVE,
        'protocol': {
            'type': 'SAML2',
            'endpoints': {
                'sso': {
                    'url': OKTA_DUMMY_URL,
                    'binding': 'HTTP-POST',
                    'destination': OKTA_DUMMY_URL,
                },
                'acs': {'binding': 'HTTP-POST', 'type': 'INSTANCE'},
            },
            'algorithms': {
                'request': {'signature': {'algorithm': 'SHA-256', 'scope': 'REQUEST'}},
                'response': {'signature': {'algorithm': 'SHA-256', 'scope': 'ANY'}},
            },
            'credentials': {
                'trust': {'issuer': OKTA_DUMMY_URL, 'kid': BASE_CERTIFICATE_ID}
            },
        },
        'policy': {
            'provisioning': {
                'action': 'AUTO',
                'profileMaster': True,
                'groups': {
                    'action': 'ASSIGN',
                    'assignments': [OKTA_GROUPS[ENVIRONMENT]],
                },
                'conditions': {
                    'deprovisioned': {'action': 'NONE'},
                    'suspended': {'action': 'NONE'},
                },
            },
            'accountLink': {'filter': None, 'action': 'AUTO'},
            'subject': {
                'userNameTemplate': {'template': 'idpuser.email'},
                'filter': '',
                'matchType': 'USERNAME',
                'matchAttribute': None,
            },
        },
    }


def generate_routing_rule_body(organization_name, idp_id, domains):
    patterns = []
    for domain in domains:
        patterns.append({'matchType': 'SUFFIX', 'value': domain})

    return {
        'status': 'ACTIVE',
        'name': organization_name,
        'priority': 1,
        'created': None,
        'lastUpdated': None,
        'system': False,
        'conditions': {
            'network': {'connection': 'ANYWHERE'},
            'platform': {
                'include': [{'type': 'ANY', 'os': {'type': 'ANY'}}],
                'exclude': [],
            },
            'userIdentifier': {'patterns': patterns, 'type': 'IDENTIFIER'},
            'app': {'include': [], 'exclude': []},
        },
        'actions': {'idp': {'providers': [{'id': idp_id, 'type': 'SAML2'}]}},
        'type': 'IDP_DISCOVERY',
    }


AZURE_PROPERTIES = {
    'definitions': {
        'custom': {
            'id': CUSTOM,
            'type': 'object',
            'properties': {
                'email': {
                    'title': 'Email',
                    'type': 'string',
                    'externalName': (
                        'http://schemas.xmlsoap.org/ws/'
                        '2005/05/identity/claims/emailaddress'
                    ),
                    'scope': 'NONE',
                },
                'firstName': {
                    'title': FIRST_NAME,
                    'type': 'string',
                    'externalName': (
                        'http://schemas.xmlsoap.org/ws/'
                        '2005/05/identity/claims/givenname'
                    ),
                    'scope': 'NONE',
                },
                'lastName': {
                    'title': LAST_NAME,
                    'type': 'string',
                    'externalName': (
                        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname'
                    ),
                    'scope': 'NONE',
                },
                'upn': {
                    'title': 'UPN',
                    'type': 'string',
                    'externalName': (
                        'http://schemas.xmlsoap.org/ws/'
                        '2005/05/identity/claims/nameidentifier'
                    ),
                    'scope': 'NONE',
                },
                'role': {
                    'title': 'Role',
                    'type': 'string',
                    'externalName': 'role',
                    'scope': 'NONE',
                },
            },
            'required': [],
        }
    }
}


def get_azure_to_okta_mappings(organization_name, organization_id):
    return {
        'properties': {
            'login': {'expression': APP_USER_EMAIL, 'pushStatus': 'PUSH'},
            'firstName': {'expression': 'appuser.firstName', 'pushStatus': 'PUSH'},
            'lastName': {'expression': 'appuser.lastName', 'pushStatus': 'PUSH'},
            'email': {'expression': APP_USER_EMAIL, 'pushStatus': 'PUSH'},
            'organization': {
                'expression': f'\"{organization_name}\"',
                'pushStatus': 'PUSH',
            },
            'organizationId': {
                'expression': f'\"{organization_id}\"',
                'pushStatus': 'PUSH',
            },
            'mobilePhone': None,
            'laikaRole': {'expression': APP_USER_ROLE, 'pushStatus': 'PUSH'},
        }
    }


OKTA_TO_AZURE_MAPPINGS = {
    'properties': {
        'firstName': None,
        'lastName': None,
        'email': None,
        'mobilePhone': None,
    }
}


OKTA_OR_GOOGLE_PROPERTIES = {
    'definitions': {
        'custom': {
            'id': CUSTOM,
            'type': 'object',
            'properties': {
                'firstName': {
                    'title': FIRST_NAME,
                    'type': 'string',
                    'required': True,
                    'externalName': 'firstName',
                    'scope': 'NONE',
                    'maxLength': 50,
                },
                'lastName': {
                    'title': LAST_NAME,
                    'type': 'string',
                    'required': True,
                    'externalName': 'lastName',
                    'scope': 'NONE',
                    'maxLength': 50,
                },
                'email': {
                    'title': 'Email',
                    'type': 'string',
                    'required': True,
                    'externalName': 'email',
                    'scope': 'NONE',
                    'maxLength': 100,
                },
                'mobilePhone': {
                    'title': 'Mobile Phone',
                    'type': 'string',
                    'externalName': 'mobilePhone',
                    'scope': 'NONE',
                    'maxLength': 100,
                },
                'login': {
                    'title': 'Login',
                    'type': 'string',
                    'externalName': 'login',
                    'scope': 'NONE',
                },
                'role': {
                    'title': 'Role',
                    'type': 'string',
                    'externalName': 'role',
                    'scope': 'NONE',
                },
            },
            'required': ['firstName', 'lastName', 'email'],
        }
    }
}


def get_client_okta_to_okta_mappings(organization_name, organization_id):
    return {
        'properties': {
            'firstName': {'expression': 'source.firstName', 'pushStatus': 'PUSH'},
            'lastName': {'expression': 'source.lastName', 'pushStatus': 'PUSH'},
            'email': {'expression': 'source.email', 'pushStatus': 'PUSH'},
            'mobilePhone': {'expression': 'source.mobilePhone', 'pushStatus': 'PUSH'},
            'login': {'expression': 'source.userName', 'pushStatus': 'PUSH'},
            'organizationId': {
                'expression': f'\"{organization_id}\"',
                'pushStatus': 'PUSH',
            },
            'organization': {
                'expression': f'\"{organization_name}\"',
                'pushStatus': 'PUSH',
            },
            'laikaRole': {'expression': APP_USER_ROLE, 'pushStatus': 'PUSH'},
        }
    }


OKTA_TO_OKTA_OR_GOOGLE_CLIENT_MAPPINGS = {
    'properties': {
        'firstName': {'expression': 'user.firstName', 'pushStatus': 'PUSH'},
        'lastName': {'expression': 'user.lastName', 'pushStatus': 'PUSH'},
        'mobilePhone': {'expression': 'user.mobilePhone', 'pushStatus': 'DONT_PUSH'},
        'email': {'expression': 'user.email', 'pushStatus': 'DONT_PUSH'},
    }
}


def get_google_to_okta_mappings(organization_name, organization_id):
    return {
        'properties': {
            'firstName': {'expression': 'appuser.firstName', 'pushStatus': 'PUSH'},
            'lastName': {'expression': 'appuser.lastName', 'pushStatus': 'PUSH'},
            'email': {'expression': APP_USER_EMAIL, 'pushStatus': 'PUSH'},
            'mobilePhone': {'expression': 'appuser.mobilePhone', 'pushStatus': 'PUSH'},
            'login': {'expression': APP_USER_EMAIL, 'pushStatus': 'PUSH'},
            'organizationId': {
                'expression': f'\"{organization_id}\"',
                'pushStatus': 'PUSH',
            },
            'organization': {
                'expression': f'\"{organization_name}\"',
                'pushStatus': 'PUSH',
            },
            'laikaRole': {'expression': APP_USER_ROLE, 'pushStatus': 'PUSH'},
        }
    }
