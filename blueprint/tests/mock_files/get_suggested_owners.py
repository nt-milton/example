from blueprint.constants import COMPLIANCE, HUMAN_RESOURCES, TECHNICAL
from user.tests import create_user


def get_suggested_owners(graphql_organization):
    return {
        COMPLIANCE: create_user(
            organization=graphql_organization, email='test+compliance@heylaika.com'
        ),
        HUMAN_RESOURCES: create_user(
            organization=graphql_organization, email='test+hr@heylaika.com'
        ),
        TECHNICAL: create_user(
            organization=graphql_organization, email='test+technical@heylaika.com'
        ),
    }
