FULL_NAME = 'full_name'
FIRST_NAME = 'first_name'
EMAIL = 'email'
CLIENT_SHORT_NAME = 'client_short_name'
CLIENT_LEGAL = 'client_legal'
REPORT_DATE = 'report_date'
TRUST_CATEGORIES = 'trust_categories'
AUDIT_FIRM_NAME = 'audit_firm_name'
PARTNER = 'partner'
STREET_ADDRESS = 'street_address'
ZIP_CODE = 'zip_code'
USERNAME = 'username'
LAST_ENGAGEMENT_DATE = 'last_engagement_date'

ENGAGEMENT_FIELDS = [
    FULL_NAME,
    CLIENT_SHORT_NAME,
    CLIENT_LEGAL,
    FIRST_NAME,
    REPORT_DATE,
    TRUST_CATEGORIES,
    EMAIL,
    AUDIT_FIRM_NAME,
    PARTNER,
    STREET_ADDRESS,
    ZIP_CODE,
    USERNAME,
]

REPRESENTATION_FIELDS = [
    CLIENT_LEGAL,
    TRUST_CATEGORIES,
    USERNAME,
    EMAIL,
    LAST_ENGAGEMENT_DATE,
]

MANAGEMENT_ASSERTION_FIELDS = [
    CLIENT_SHORT_NAME,
    CLIENT_LEGAL,
    TRUST_CATEGORIES,
    USERNAME,
    EMAIL,
]

SUBSEQUENT_EVENTS_FIELDS = [CLIENT_LEGAL, USERNAME, EMAIL]

CONTROL_DESIGN_ASSESSMENT_FIELDS = [FULL_NAME, EMAIL, USERNAME]

DOCUSIGN_FIELDS = {
    FULL_NAME: 'Fullname',
    FIRST_NAME: 'firstname',
    EMAIL: 'Email',
    CLIENT_SHORT_NAME: 'clientshortname',
    CLIENT_LEGAL: 'clientlegal',
    REPORT_DATE: 'reportdate',
    TRUST_CATEGORIES: 'trustcategories',
    AUDIT_FIRM_NAME: 'auditfirmname',
    PARTNER: 'partner',
    STREET_ADDRESS: 'streetaddress',
    ZIP_CODE: 'csz',
    USERNAME: 'UserName',
    LAST_ENGAGEMENT_DATE: 'lastengagementdate',
}


def get_parse_fields(docusign_fields, fields):
    url_fields_in_dict = {field: docusign_fields[field] for field in fields}

    parsed = {}
    for key, value in url_fields_in_dict.items():
        if value is not None:
            parsed[DOCUSIGN_FIELDS[key]] = value

    return parsed
