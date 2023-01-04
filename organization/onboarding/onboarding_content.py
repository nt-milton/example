from typing import TypedDict

from django.db import connection


class TypeformContact(TypedDict, total=False):
    email_address: str
    first_name: str
    last_name: str


def get_onboarding_form_answer(organization, reference_name, question_type):
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT responses->>%(question_type)s
            FROM organization_onboardingresponse,
            jsonb_array_elements(questionary_response) responses
            WHERE responses->'field'->>'ref' = %(reference_name)s
            AND organization_id = %(organization_id)s
            ''',
            {
                'organization_id': organization.id,
                'reference_name': reference_name,
                'question_type': question_type,
            },
        )

        return cursor.fetchone()


def get_onboarding_form_text_answer(organization, reference_name):
    answer = get_onboarding_form_answer(organization, reference_name, 'text')
    if not answer:
        return None

    return answer[0]


"""key: Typeform user choice - Value: vendor name"""
vendor_names_mapper = {
    "ADP WorkforceNow": "ADP Workforce Now",
    "Amazon Web Services": "AWS",
    "Bob": "HiBob",
    "Github": "Github Apps",
    "Paychex": "Paychex Flex",
    "Rippling": "Rippling HR",
    "Run by ADP": "Run Powered by ADP",
    "Digital Ocean": "DigitalOcean",
    "Jumpcloud": "JumpCloud",
}


def get_onboarding_vendor_names(answer, vendor_questions, mapper: dict[str, str]):
    vendor_names: list[str] = []
    ref_answer = answer.get('field', {}).get('ref')
    if ref_answer in vendor_questions:
        if answer['type'] == 'choice':
            typeform_vendor_name = answer.get('choice', {}).get('label', '')
            vendor_names.append(mapper.get(typeform_vendor_name, typeform_vendor_name))
        elif answer['type'] == 'choices':
            typeform_vendors_multiple = answer.get('choices', {}).get('labels', [])
            for typeform_vendor_name in typeform_vendors_multiple:
                vendor_names.append(
                    mapper.get(typeform_vendor_name, typeform_vendor_name)
                )
        elif answer['type'] == 'boolean' and answer['boolean']:
            vendor_names.append('Slack')
    return vendor_names


def get_onboarding_contact(answer, contact_questions, contact):
    ref_answer = answer.get('field', {}).get('ref')
    if ref_answer in contact_questions:
        property_name = '_'.join(ref_answer.rsplit('_')[-2:])
        property_value = answer.get('text') or answer.get('email')
        contact[property_name] = property_value
        return contact
    return contact


def map_answer(ref_answer, answer):
    key = '_'.join(ref_answer.rsplit('_')[-2:])
    value = answer.get('text', None) or answer.get('email', None)
    return {
        key: key,
        value: value,
    }


def get_onbording_contacts_questions():
    contact_questions = []
    contact_questions.extend(CONTACT_QUESTIONS['primary_hr'])
    contact_questions.extend(CONTACT_QUESTIONS['primary_compliance'])
    contact_questions.extend(CONTACT_QUESTIONS['primary_technical'])
    contact_questions.extend(HIMSELF_QUESTIONS)
    return contact_questions


def get_onboarding_contacts(questionary_responses: dict, user):
    """Return a list of contacts in the questionary response."""
    contact_questions = get_onbording_contacts_questions()
    # excluding questions that are not contact related
    contact_answers = [
        answer
        for answer in questionary_responses
        if answer.get('field', {}).get('ref') in contact_questions
    ]

    contacts = []
    contact = {}
    for answer in contact_answers:
        ref_answer = answer.get('field', {}).get('ref')
        if ref_answer in HIMSELF_QUESTIONS:
            # create the contact if the user is the POC
            if answer.get('boolean'):
                if user is None:
                    continue
                contacts.append(
                    {
                        'email_address': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'role': get_contact_role_by_ref_answer(ref_answer),
                    }
                )
            # assign the role from typeform if the user is not POC
            contact['role'] = get_contact_role_by_ref_answer(ref_answer)
            continue
        key, value = map_answer(ref_answer, answer)
        contact[key] = value
        if len(contact) == 4:
            contacts.append(contact)
            # reset the contact
            contact = {}
    return contacts


def get_contact_role_by_ref_answer(answer_ref: str):
    roles_mapper = {
        IS_HR_POC_QUESTION: 'Human Resources',
        IS_TECHNICAL_POC_QUESTION: 'Technical',
        IS_COMPLIANCE_POC_QUESTION: 'Compliance',
    }
    return roles_mapper.get(answer_ref, None)


def get_technical_poc_answer(answer):
    ref_answer = answer.get('field', {}).get('ref')
    if ref_answer == IS_TECHNICAL_POC_QUESTION:
        return answer.get('boolean')


VENDOR_QUESTIONS = [
    'organization_infrastructure_tools',
    'organization_ticket_system',
    'organization_mdm_solution',
    'organization_version_control_system',
    'organization_monitoring_logging_system',
    'organization_business_suite',
    'organization_sign_on_system',
    'organization_payroll_provider',
    'organization_slack',
]

IS_HR_POC_QUESTION = 'is_hr_poc'
IS_TECHNICAL_POC_QUESTION = 'is_technical_poc'
IS_COMPLIANCE_POC_QUESTION = 'is_compliance_poc'

HIMSELF_QUESTIONS = [
    IS_HR_POC_QUESTION,
    IS_TECHNICAL_POC_QUESTION,
    IS_COMPLIANCE_POC_QUESTION,
]


CONTACT_QUESTIONS = {
    'primary_compliance': [
        'primary_contact_email_address',
        'primary_contact_first_name',
        'primary_contact_last_name',
    ],
    'primary_technical': [
        'primary_technical_contact_email_address',
        'primary_technical_contact_first_name',
        'primary_technical_contact_last_name',
    ],
    'primary_hr': [
        'primary_hr_contact_email_address',
        'primary_hr_contact_first_name',
        'primary_hr_contact_last_name',
    ],
}
