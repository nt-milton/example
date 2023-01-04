from django.db import models


class ControlBlueprintStatus(models.TextChoices):
    IMPLEMENTED = ('IMPLEMENTED',)
    NOT_IMPLEMENTED = 'NOT IMPLEMENTED'
