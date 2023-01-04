import functools
import hashlib
import json
import logging
from typing import Any, Callable, Dict

from django.db import models
from django.db.models import DateField, JSONField, Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast

from alert.models import Alert
from laika.utils.query_builder import EMPTY_OPERATORS
from organization.models import Organization
from user.models import User

from .constants import ATTRIBUTES_TYPE
from .metadata import Metadata
from .types import AttributeTypeFactory, Types, format_users

logger = logging.getLogger(__name__)


def hash_laika_object_data(data: Dict[str, Any]) -> str:
    sha256_hash = hashlib.sha256()
    encoded_data = json.dumps(data, sort_keys=True).encode()
    sha256_hash.update(encoded_data)
    return sha256_hash.hexdigest()


def laika_object_type_logo_path(instance, filename):
    return f'{instance.organization.id}/object_types/{instance.type_name}/{filename}'


class LaikaObjectType(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='laika_object_types'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    display_name = models.CharField(max_length=100)
    type_name = models.CharField(max_length=100)
    color = models.CharField(max_length=100)
    icon_name = models.CharField(max_length=100)
    display_index = models.IntegerField()
    is_system_type = models.BooleanField(default=False)
    # Leave it as max_lenght=500 it support markdown
    description = models.CharField(max_length=500, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'type_name'],
                name='unique_type_name_for_organization',
            )
        ]

    def __str__(self):
        return f'{self.display_name} ({self.organization.name})'

    def get_attribute_type_by_name(self, name):
        return AttributeTypeFactory.get_attribute_type(self.attributes.get(name=name))

    def get_filter_query(self, filter_by):
        """Filter all fields based on their type

        For each field:
        - Get the type name from the attributes list
        - Get the corresponding type
        - Get the filter Query for that type
        """
        filter_query = Q()
        for field, value in filter_by.items():
            attribute_type = self.get_attribute_type_by_name(field)
            field_filter_query = attribute_type.get_filter_query(field, value)
            filter_query.add(field_filter_query, Q.AND)

        return filter_query

    def get_incredible_filter_query(self, filters):
        filter_query = Q()

        for element in filters:
            field = element['field']
            value = element.get('value', '')
            operator = element['operator']

            attribute_type = self.get_attribute_type_by_name(field)
            field_filter_query = attribute_type.get_incredible_filter_query(
                field=f'data__{field}', value=value, operator=operator
            )
            filter_query.add(field_filter_query, Q.AND)

        return filter_query

    def get_annotate(self, filters):
        annotate = {}

        for element in filters:
            field = element['field']
            operator = element['operator'].upper()
            attribute_type = self.get_attribute_type_by_name(field)

            are_operators_not_empty = operator not in EMPTY_OPERATORS

            if (
                attribute_type.OPERATOR_TYPE == ATTRIBUTES_TYPE['NUMBER']
                and are_operators_not_empty
            ):
                annotate.update(
                    {f'data__{field}': RawSQL("((data->>%s)::numeric)", (field,))}
                )

            if (
                attribute_type.OPERATOR_TYPE == ATTRIBUTES_TYPE['DATE']
                and are_operators_not_empty
            ):
                annotate.update(
                    {
                        f'data__{field}': Cast(
                            RawSQL("((data->>%s)::timestamp)", (field,)), DateField()
                        )
                    }
                )

        return annotate

    def get_order_by(self, order_by):
        """Order field based on their type

        For each field:
        - Get the type name from the attributes list
        - Get the corresponding type
        - Get the order string for that type
        """
        if order_by:
            field = order_by.get('field')
            attribute_type = self.get_attribute_type_by_name(field)
            return attribute_type.get_order_by(order_by)
        # Default order by element created_at (not by data values)
        return 'created_at'


class Attribute(models.Model):
    object_type = models.ForeignKey(
        LaikaObjectType, on_delete=models.CASCADE, related_name='attributes'
    )
    name = models.CharField(max_length=60)
    sort_index = models.IntegerField()
    attribute_type = models.CharField(max_length=100, choices=Types.choices())
    min_width = models.IntegerField(blank=True)
    is_manually_editable = models.BooleanField(default=True)
    is_required = models.BooleanField(default=False)
    _metadata = JSONField()

    def __str__(self):
        return self.name

    @property
    def metadata(self):
        return Metadata(self._metadata)

    def save(self, *args, **kwargs):
        # Change type to TEXT if no select options are present
        if (
            self.attribute_type == Types.SINGLE_SELECT.name
            and not self.metadata.select_options
        ):
            self.attribute_type = Types.TEXT.name
            logger.warning(
                f'Attribute "{self.name}" for Object Type '
                f'{self.object_type.id} has missing options.'
                ' Type changed from SINGLE_SELECT to TEXT.'
            )

        attribute_type = AttributeTypeFactory.get_attribute_type(self)
        if not self.min_width:
            self.min_width = attribute_type.get_min_width()

        super(Attribute, self).save(*args, **kwargs)


class LaikaObject(models.Model):
    class Meta:
        permissions = [
            ('bulk_upload_object', 'Can bulk upload object'),
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    object_type = models.ForeignKey(
        LaikaObjectType, on_delete=models.CASCADE, related_name='elements'
    )
    data = JSONField()
    is_manually_created = models.BooleanField(default=False)
    connection_account = models.ForeignKey(
        'integration.ConnectionAccount',
        on_delete=models.DO_NOTHING,
        related_name='laika_objects',
        blank=True,
        null=True,
    )
    data_hash = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return json.dumps(self.data)

    @property
    def hash_data_object(self):
        return hash_laika_object_data(self.data)

    def save(self, *args, **kwargs):
        object_type = self.object_type
        format_user_data_type = build_format_user_data_type(
            object_type.organization_id, object_type.id
        )
        format_user_data_type(self.data)

        self.data_hash = self.hash_data_object
        super(LaikaObject, self).save(*args, **kwargs)


class LaikaObjectAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='laika_object_alert', on_delete=models.CASCADE
    )
    laika_object = models.ForeignKey(
        LaikaObject, related_name='alerts', on_delete=models.CASCADE
    )


@functools.lru_cache(maxsize=1)
def build_format_user_data_type(
    organization_id: str, laika_object_type_id: int
) -> Callable[[dict], None]:
    user_attributes = [
        att
        for att in Attribute.objects.filter(
            object_type_id=laika_object_type_id, attribute_type=Types.USER.name
        )
    ]
    if not user_attributes:
        return lambda _: None

    users = {
        user.email: user
        for user in User.objects.filter(
            organization=organization_id, deleted_at__isnull=True
        )
    }

    def format_lo_data(data: dict):
        for att in user_attributes:
            value = data.get(att.name)
            if value and isinstance(value, str):
                f_value = format_users(value, att, users)
                if isinstance(f_value, list):
                    f_value = f_value[0]
                data[att.name] = f_value

    return format_lo_data
