import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from pyairtable import Api
from pyairtable.formulas import match

from blueprint.models import Page
from user.models import User

logger = logging.getLogger(__name__)


def execute_airtable_request(api_key: str, query: Dict):
    return Api(api_key).all(**query)


class AirtableSync(object):
    def __init__(
        self,
        table_name: str,
        blueprint_name,
        required_fields: List[str],
        request_user: User,
        formula: Dict = None,
        raw_formula: str = '',
        related_table_records: Dict = None,
    ):
        self.table_name: str = table_name
        self.blueprint_name: str = blueprint_name
        self.required_fields: List[str] = required_fields
        self.request_user = request_user
        self.formula: Optional[Dict] = formula
        self.raw_formula: Optional[str] = raw_formula
        self.related_table_records = related_table_records

        self.api_key: str = ''
        self.base_id: str = ''
        self.status_detail: List[str] = []

        blueprint = Page.objects.get(name=self.blueprint_name)
        self.api_key = blueprint.airtable_api_key
        self.base_id = blueprint.airtable_link

    def get_airtable_single_record(self, record_id):
        query = {
            'base_id': self.base_id,
            'table_name': self.table_name,
            'record_id': record_id,
        }

        return Api(self.api_key).get(**query)

    def get_airtable_records(self) -> List[Dict]:
        query = {'base_id': self.base_id, 'table_name': self.table_name}

        if self.formula:
            query.update({'formula': match(self.formula)})

        elif self.raw_formula:
            query.update({'formula': self.raw_formula})
        try:
            return execute_airtable_request(self.api_key, query)
        except Exception as e:
            message = f'Error getting airtable records: {e}'
            logger.warning(message)
            self.status_detail.append(message)
            return []

    def update_single_record_of_blueprint(self, record_id, upsert_object):
        self.status_detail = []
        blueprint = Page.objects.get(name=self.blueprint_name)
        try:
            record = self.get_airtable_single_record(record_id)
            fields = self.get_record_fields(record)

            if fields:
                created_model, _ = upsert_object(fields, self.request_user, None)
                if created_model:
                    logger.info(f'Record upserted successfully: {created_model}')
            blueprint.status_detail = '\n'.join(self.status_detail)
        except Exception as e:
            message = f'Error updating blueprint: {e}'
            logger.warning(message)
            blueprint.status_detail = message

        blueprint.synched_at = datetime.now()
        blueprint.save()
        logger.info('Sync was done successfully')

    def update_blueprint(self, upsert_object, delete_object=None) -> bool:
        self.status_detail = []
        blueprint = Page.objects.get(name=self.blueprint_name)
        try:
            self.iterate_records(
                upsert_object=upsert_object, delete_object=delete_object
            )
            blueprint.status_detail = '\n'.join(self.status_detail)
        except Exception as e:
            message = f'Error updating blueprint: {e}'
            logger.warning(message)
            blueprint.status_detail = message
            return False

        blueprint.synched_at = datetime.now()
        blueprint.save()
        logger.info('Sync was done successfully')
        return True

    def iterate_records(
        self,
        upsert_object: Callable[
            [Dict, User, Optional[Dict]], Tuple[object, bool, bool]
        ],
        delete_object: Callable[[List, User], List[str]] = None,
    ):
        reference_ids = []

        records = self.get_airtable_records()
        for record in records:
            fields = self.get_record_fields(record)

            if not fields:
                continue

            if delete_object:
                reference_ids.append(fields)

            try:
                created_model, created, updated = upsert_object(
                    fields, self.request_user, self.related_table_records
                )

                if created:
                    message = f'Record created successfully: {created_model}'
                    self.status_detail.append(message)
                    logger.info(message)
                elif updated:
                    message = f'Record updated successfully: {created_model}'
                    self.status_detail.append(message)
                    logger.info(message)

            except Exception as e:
                message = f'Error upserting this record {record}: \nTrace: {e} \n\n'
                self.status_detail.append(message)
                logger.warning(message)

        if delete_object:
            deleted_controls = delete_object(reference_ids, self.request_user)

            message = f'Records deleted: {deleted_controls}'
            self.status_detail.append(message)
            logger.info(message)

    def get_record_fields(self, record) -> Dict:
        if not self.validate_fields(record):
            self.status_detail.append(
                f'Record {record} is not valid.'
                f'Missing required fields: {self.required_fields}'
            )
            return {}

        fields = record.get('fields')
        fields.update({'airtable_record_id': record.get('id')})

        return fields

    def validate_fields(self, record: Dict) -> bool:
        fields = record.get('fields')
        if not fields or not record.get('id'):
            return False

        if self.are_fields_required_empty(fields):
            return False

        return True

    def are_fields_required_empty(self, dictionary: Dict) -> bool:
        return any(
            not dictionary.get(field) or dictionary.get(field) == '\n'
            for field in self.required_fields
        )
