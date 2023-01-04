from django.db import models


class SuggestedOwner(models.TextChoices):
    TECHNICAL = 'Technical'
    HUMAN_RESOURCES = 'Human Resources'
    COMPLIANCE = 'Compliance'
