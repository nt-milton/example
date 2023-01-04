import reversion
from django.db import models

from alert.models import Alert
from laika.constants import CATEGORIES
from laika.storage import PrivateMediaStorage
from organization.models import Organization
from search.search import searchable_model
from user.constants import USER_ROLES
from user.models import User


def training_file_directory_path(instance, filename):
    return f'{instance.organization.id}/trainings/{instance.name}/{filename}'


def generate_default_roles():
    return [val for val in USER_ROLES.values() if 'SuperAdmin' != val]


@searchable_model(type='training')
@reversion.register(follow=['alumni'])
class Training(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    roles = models.JSONField(default=generate_default_roles)
    name = models.CharField(max_length=255)
    category = models.CharField(
        max_length=100, choices=CATEGORIES, default='', blank=True
    )
    description = models.TextField(blank=True)
    slides = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=training_file_directory_path,
        blank=True,
        max_length=512,
    )

    def __str__(self):
        return self.name


class Alumni(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    training_name = models.CharField(max_length=255, blank=True)
    training_category = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='trainings', null=True
    )
    training = models.ForeignKey(
        Training, on_delete=models.CASCADE, related_name='alumni', null=True
    )

    class Meta:
        verbose_name_plural = 'alumni'

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        self.first_name = self.user.first_name
        self.last_name = self.user.last_name
        self.email = self.user.email
        self.training_name = self.training.name
        self.training_category = self.training.category
        super(Alumni, self).save(*args, **kwargs)


class TrainingAssignee(models.Model):
    user = models.ForeignKey(
        User,
        related_name='assigned_trainings',
        on_delete=models.CASCADE,
    )
    training = models.ForeignKey(
        Training,
        related_name='assignees',
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name_plural = 'TrainingAssignee'

    def __str__(self):
        return f'{str(self.user)} - {str(self.training)}'


class TrainingAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='training_alert', on_delete=models.CASCADE
    )
    training = models.ForeignKey(
        Training,
        related_name='alerts',
        on_delete=models.CASCADE,
    )
