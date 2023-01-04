import uuid
from datetime import datetime

import django.utils.timezone as timezone
import pytz
from django.db import models

from laika.settings import DJANGO_SETTINGS
from organization.models import Organization

API_URL = DJANGO_SETTINGS.get('LAIKA_APP_URL')


class Link(models.Model):
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='links'
    )
    url = models.TextField(unique=True)
    expiration_date = models.DateTimeField(blank=True, null=True)
    time_zone = models.CharField(max_length=100, blank=True, null=True)
    is_enabled = models.BooleanField(default=False)

    @property
    def is_expired(self):
        if not self.expiration_date:
            return False
        if self.time_zone:
            timezone.activate(pytz.timezone(self.time_zone))
            return timezone.localtime(timezone.now()) > self.expiration_date
        return datetime.now(tz=timezone.utc) > self.expiration_date

    @property
    def is_valid(self):
        return not self.is_expired and self.is_enabled

    @property
    def public_url(self):
        return f'{API_URL}/link/{self.id}'

    class Meta:
        verbose_name_plural = 'links'

    def __str__(self):
        return self.url
