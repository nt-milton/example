import graphene
from django.db.models import JSONField
from graphene_django.converter import convert_django_field

from .celery import app as celery_app


@convert_django_field.register(JSONField)
def jsonfield_convert_jsonstring(field, registry=None):
    return graphene.JSONString()


__all__ = ('celery_app',)
