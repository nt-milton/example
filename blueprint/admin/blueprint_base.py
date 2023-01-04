import logging
from datetime import datetime
from multiprocessing.pool import ThreadPool
from typing import List, Optional, Tuple

import reversion
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path
from reversion.admin import VersionAdmin

from blueprint.commons import AirtableSync
from blueprint.constants import RESPONSE_REDIRECT_PATH
from blueprint.models import Page
from user.models import User

logger = logging.getLogger(__name__)
pool = ThreadPool()


class BlueprintAdmin(VersionAdmin):
    blueprint_page_name = ''
    airtable_tab_name = ''
    blueprint_required_fields = []
    blueprint_formula = {}

    blueprint_parameter_name_value = ''
    model_parameter_name = ''

    blueprint_model = None

    actions = None
    change_list_template = 'admin/control_change_list.html'
    change_form_template = 'admin/blueprint_change_form.html'

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('prescribe_blueprint/', self.prescribe_blueprint),
            path('sync_from_airtable/', self.sync_from_airtable),
            path(
                '<str:record_id>/change/sync_record_from_airtable/',
                self.sync_record_from_airtable,
            ),
        ]
        return custom_urls + urls

    def should_show_prescribe_button(self) -> bool:
        return False

    def changelist_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['should_show_prescribe'] = self.should_show_prescribe_button()
        return super(BlueprintAdmin, self).changelist_view(request, extra_context)

    def prescribe_blueprint(self, request):
        logger.info(f'REQUEST: {request}')
        return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)

    def sync_record_from_airtable(self, request, record_id):
        airtable, message = self.get_airtable_for_blueprint(request)
        if not airtable and message:
            messages.warning(request, message)
            return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)

        if airtable:
            airtable.update_single_record_of_blueprint(
                self.blueprint_model.objects.get(id=record_id).airtable_record_id,
                upsert_object=self.update_or_create_object,
            )

            messages.info(request, 'Object updated!')

        return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)

    def sync_from_airtable(self, request):
        airtable, message = self.get_airtable_for_blueprint(request)
        if not airtable and message:
            messages.warning(request, message)
            return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)

        pool.apply_async(self.init_update, args=(airtable,))
        messages.info(request, 'Sync is running in the background')
        return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)

    def init_update(self, airtable: Optional[AirtableSync]) -> bool:
        if airtable:
            return airtable.update_blueprint(
                upsert_object=self.update_or_create_object,
                delete_object=self.delete_objects,
            )
        return False

    def get_default_fields(
        self, fields: dict, related_records: Optional[dict]
    ) -> Optional[dict]:
        return None

    def update_or_create_object(
        self, fields: dict, request_user: User, related_table_records: Optional[dict]
    ):
        updated = False
        defaults = {
            'airtable_record_id': fields.get('airtable_record_id'),
            'updated_at': datetime.strptime(
                fields.get('Last Modified'), '%Y-%m-%dT%H:%M:%S.%f%z'  # type: ignore
            ),
        }

        extra_defaults = self.get_default_fields(fields, related_table_records)

        if extra_defaults:
            defaults.update(**extra_defaults)  # type: ignore

        value = fields.get(self.blueprint_parameter_name_value)
        with reversion.create_revision():
            reversion.set_comment('Synched from Airtable')
            reversion.set_user(request_user)

            (
                django_object,
                created,
            ) = self.blueprint_model.objects.get_or_create(  # type: ignore
                **{self.model_parameter_name: value}, defaults=defaults
            )

            if created:
                self.execute_after_update_or_create(fields, django_object)

            elif was_modified(defaults, django_object):
                self.blueprint_model.objects.filter(  # type: ignore
                    **{self.model_parameter_name: value}
                ).update(**defaults)

                django_object = self.blueprint_model.objects.get(  # type: ignore
                    **{self.model_parameter_name: value}
                )

                self.execute_after_update_or_create(fields, django_object)
                updated = True

        return django_object, created, updated

    def execute_after_update_or_create(self, fields: dict, django_object):
        return False

    def delete_objects(
        self, objects_to_exclude: List[dict], request_user: User
    ) -> List[str]:
        airtable_records = self.get_records_by_attr(objects_to_exclude)

        objects_to_delete = self.blueprint_model.objects.exclude(  # type: ignore
            **{f'{self.model_parameter_name}__in': airtable_records}
        )

        objects_deleted = []
        for deleted_object in objects_to_delete:
            with reversion.create_revision():
                reversion.set_comment('Deleted from Airtable')
                reversion.set_user(request_user)

                objects_deleted.append(f'{deleted_object}')
                deleted_object.delete()

        return objects_deleted

    def get_records_by_attr(self, objects_to_exclude: List[dict]):
        return [
            excluded_object.get(self.blueprint_parameter_name_value)
            for excluded_object in objects_to_exclude
        ]

    def get_airtable_for_blueprint(self, request) -> Tuple[Optional[AirtableSync], str]:
        if not self.validate_configuration_attrs():
            return (
                None,
                'This admin page is not well configured. '
                'Some attributes are empty or None',
            )

        airtable = self.get_airtable_sync_class(request)
        if not airtable:
            return None, 'Blueprint configuration does not exist'

        return airtable, ''

    def get_related_table_records(self, request) -> Optional[dict]:
        return None

    def get_airtable_sync_class(self, request) -> Optional[AirtableSync]:
        if not Page.objects.filter(name=self.blueprint_page_name).exists():
            return None

        airtable = AirtableSync(
            table_name=self.airtable_tab_name,
            blueprint_name=self.blueprint_page_name,
            required_fields=self.blueprint_required_fields,
            request_user=request.user,
        )

        related_records = self.get_related_table_records(request)
        if related_records:
            airtable.related_table_records = related_records

        if self.blueprint_formula:
            airtable.formula = self.blueprint_formula

        return airtable

    def validate_configuration_attrs(self):
        return all(
            [
                self.airtable_tab_name,
                self.blueprint_page_name,
                self.blueprint_required_fields,
                self.blueprint_model,
                self.model_parameter_name,
                self.blueprint_parameter_name_value,
            ]
        )


def was_modified(defaults: dict, django_object):
    return defaults.get('updated_at') > django_object.updated_at
