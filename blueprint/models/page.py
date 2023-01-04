from django.core.exceptions import ValidationError
from django.db import models

from blueprint.choices.blueprint_pages import BlueprintPage
from user.models import User


class Page(models.Model):
    class Meta:
        verbose_name_plural = '[Global Blueprint]'

    name = models.CharField(
        unique=True,
        max_length=1024,
        choices=BlueprintPage.choices,
        default=BlueprintPage.CONTROLS,
    )

    airtable_link = models.CharField(
        max_length=2000, blank=True, verbose_name='Airtable Base ID'
    )
    airtable_api_key = models.CharField(max_length=2000, blank=True)

    created_by = models.ForeignKey(
        User,
        related_name='blueprint_pages',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status_detail = models.TextField(blank=True)
    synched_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean_fields(self, exclude=None):
        if self.name == BlueprintPage.GLOBAL and (
            not self.airtable_api_key or not self.airtable_link
        ):
            raise ValidationError(
                'Airtable Link and api key are required for Global Blueprint'
            )

        elif self.name != BlueprintPage.GLOBAL:
            raise ValidationError(
                'You are not allowed to add single blueprints. '
                'Please add or edit the Global Blueprint to reflect all '
                'changes.'
            )
        elif self.name != BlueprintPage.GLOBAL and self.airtable_api_key:
            raise ValidationError(
                'Api Key value is not allowed in this Blueprint. '
                'Please add it to the Global'
            )

        elif (
            self.name != BlueprintPage.GLOBAL
            and not Page.objects.filter(name=BlueprintPage.GLOBAL).first()
        ):
            raise ValidationError(
                f'In order to create {self.name} Blueprint, you need to '
                'create the Global Blueprint first. '
            )

        super().clean_fields(exclude=exclude)
