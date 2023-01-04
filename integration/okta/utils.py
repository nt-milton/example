from collections import namedtuple

OktaRequest = namedtuple('OktaRequest', ('user', 'groups', 'applications', 'factors'))

SUPER_ADMIN_TYPE = 'SUPER_ADMIN'

OKTA_SYSTEM = 'Okta'

ACTIVE = 'ACTIVE'

SUB_DOMAIN_REGEX = r'[-.a-zA-Z0-9]+\.okta\.com'

SIMPLE_DOMAIN_REGEX = r'^[a-zA-Z]+$'

API_LIMIT = [1, 0]
