from urllib.parse import quote, unquote, urlencode

from .docusign_fields import (
    AUDIT_FIRM_NAME,
    CLIENT_LEGAL,
    CLIENT_SHORT_NAME,
    CONTROL_DESIGN_ASSESSMENT_FIELDS,
    EMAIL,
    ENGAGEMENT_FIELDS,
    FIRST_NAME,
    FULL_NAME,
    LAST_ENGAGEMENT_DATE,
    MANAGEMENT_ASSERTION_FIELDS,
    PARTNER,
    REPORT_DATE,
    REPRESENTATION_FIELDS,
    STREET_ADDRESS,
    SUBSEQUENT_EVENTS_FIELDS,
    TRUST_CATEGORIES,
    USERNAME,
    ZIP_CODE,
    get_parse_fields,
)


def get_docusign_query_string_from_fields(prefix="Client_", **fields):
    if prefix is None or not isinstance(prefix, str):
        raise ValueError('Invalid prefix')

    fields_with_prefix = {f'{prefix}{key}': val for key, val in fields.items()}
    query_string = urlencode(fields_with_prefix, quote_via=quote)
    return unquote(query_string)


def get_query_string_from_fields(docusign_fields, fields_to_pick):
    parsed_fields = get_parse_fields(docusign_fields, fields_to_pick)
    return f'&{get_docusign_query_string_from_fields(**parsed_fields)}'


def get_organization_address(org):
    address = org.billing_address
    street_address, zip_code = None, None

    if address:
        street_address = f'{address.street1} {address.street2}'
        zip_code = f'{address.city} {address.state} {address.zip_code}'

    return street_address, zip_code


def generate_docusign_fields(user, audit):
    audit_configuration = audit.audit_configuration
    organization = user.organization

    street_address, zip_code = get_organization_address(organization)

    docusign_fields = {
        FULL_NAME: user.get_full_name(),
        CLIENT_SHORT_NAME: 'Laika',
        CLIENT_LEGAL: user.organization.name,
        FIRST_NAME: user.first_name,
        REPORT_DATE: audit_configuration.get('as_of_date'),
        TRUST_CATEGORIES: ','.join(audit_configuration['trust_services_categories']),
        EMAIL: user.email,
        AUDIT_FIRM_NAME: audit.audit_firm.name if audit.audit_firm else None,
        PARTNER: None,
        STREET_ADDRESS: street_address,
        ZIP_CODE: zip_code,
        USERNAME: user.get_full_name(),
        LAST_ENGAGEMENT_DATE: audit_configuration.get('as_of_date'),
    }

    return {
        'engagement_letter_url': get_query_string_from_fields(
            docusign_fields, ENGAGEMENT_FIELDS
        ),
        'representation_letter_url': get_query_string_from_fields(
            docusign_fields, REPRESENTATION_FIELDS
        ),
        'management_assertion_url': get_query_string_from_fields(
            docusign_fields, MANAGEMENT_ASSERTION_FIELDS
        ),
        'subsequent_events_url': get_query_string_from_fields(
            docusign_fields, SUBSEQUENT_EVENTS_FIELDS
        ),
        'control_design_assessment_url': get_query_string_from_fields(
            docusign_fields, CONTROL_DESIGN_ASSESSMENT_FIELDS
        ),
    }
