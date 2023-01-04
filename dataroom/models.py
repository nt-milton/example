import enum

from django.db import models

from evidence.models import Evidence
from organization.models import Organization
from search.search import searchable_model
from user.models import User


@searchable_model(type='dataroom')
class Dataroom(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='dataroom'
    )
    evidence = models.ManyToManyField(
        Evidence, related_name='dataroom', through='DataroomEvidence'
    )
    name = models.CharField(max_length=512)
    owner = models.ForeignKey(
        User,
        related_name='dataroom_owned',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_soft_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class DataroomEvidence(models.Model):
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE)
    dataroom = models.ForeignKey(
        Dataroom, on_delete=models.CASCADE, related_name='dataroom_evidence'
    )

    def __str__(self):
        return str(self.evidence)


class DaysOrderBy(enum.Enum):
    FIELD = 'time'
    FILTERS = [('LAST_SEVEN_DAYS', 7), ('LAST_MONTH', 30), ('LAST_QUARTER', 120)]
