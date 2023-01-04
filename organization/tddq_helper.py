import logging
from copy import deepcopy
from typing import Dict, List

from pyairtable import Api

from organization.constants import (
    AIRTABLE_API_KEY,
    FIELDS,
    ORG_ID,
    ORG_NAME,
    QUESTION,
    QUESTION_RESPONSE,
    TDDQ_BASE_ID,
    TDDQ_STRUCTURED_TABLE,
)
from organization.models import Organization

logger = logging.getLogger(__name__)


def execute_airtable_request(query: Dict):
    return Api(AIRTABLE_API_KEY).all(**query)


def execute_airtable_batch_create(records: list[dict]):
    return Api(AIRTABLE_API_KEY).batch_create(
        base_id=TDDQ_BASE_ID,
        table_name=TDDQ_STRUCTURED_TABLE,
        records=records,
        typecast=True,
    )


def execute_airtable_batch_update(records: list[dict]):
    return Api(AIRTABLE_API_KEY).batch_update(
        base_id=TDDQ_BASE_ID,
        table_name=TDDQ_STRUCTURED_TABLE,
        records=records,
        typecast=True,
    )


def get_airtable_records(table_name: str, formula: str) -> List[Dict]:
    query = {'base_id': TDDQ_BASE_ID, 'table_name': table_name, 'formula': formula}

    try:
        return execute_airtable_request(query)
    except Exception as e:
        message = f'Error getting airtable records: {e}'
        logger.warning(message)
        return []


def get_options_from_list(question_response):
    attachments = []
    options = []
    for option in question_response:
        if isinstance(option, str):
            options.append(option)
        elif isinstance(option, dict) and option.get('url'):
            options.append(option['url'])
            attachments.append(
                {'url': option.get('url'), 'filename': option.get('filename')}
            )
    return deepcopy(options), deepcopy(attachments)


def get_formatted_data(airtable_row: Dict, metadata: List[Dict]) -> List[Dict]:
    updated_metadata = []
    for question in metadata:
        if not airtable_row[FIELDS].get(ORG_ID):
            break
        try:
            organization = Organization.objects.get(id=airtable_row[FIELDS][ORG_ID])
            question[FIELDS][ORG_ID] = str(organization.id)
            question[FIELDS][ORG_NAME] = organization.name
        except Organization.DoesNotExist:
            org_id = airtable_row[FIELDS].get(ORG_ID)
            logger.warning(f'Organization with ID: {org_id} does not exist')
            break

        question_response = airtable_row[FIELDS].get(question[FIELDS][QUESTION])

        if isinstance(question_response, list):
            options, attachments = get_options_from_list(question_response)
            question[FIELDS][QUESTION_RESPONSE] = ', '.join(options)
            question[FIELDS]['Attachments'] = attachments
        elif isinstance(question_response, str):
            question[FIELDS][QUESTION_RESPONSE] = question_response
        elif isinstance(question_response, bool):
            question[FIELDS][QUESTION_RESPONSE] = str(question_response)

        updated_metadata.append(question[FIELDS])
    return updated_metadata


def update_or_create_airtable_records(
    current_structured: list[dict], new_records: list[list[dict]]
):
    records_to_create = []
    records_to_update = []
    for organization_records in new_records:
        for record in organization_records:
            org_id = record[ORG_ID]
            question = record[QUESTION]
            existing_record = next(
                (
                    current_record
                    for current_record in current_structured
                    if current_record[FIELDS][ORG_ID] == org_id
                    and current_record[FIELDS][QUESTION] == question
                ),
                None,
            )
            if not existing_record:
                records_to_create.append(record)
            else:
                records_to_update.append(
                    {'id': existing_record['id'], 'fields': record}
                )

    if len(records_to_create):
        execute_airtable_batch_create(records_to_create)
    if len(records_to_update):
        execute_airtable_batch_update(records_to_update)
