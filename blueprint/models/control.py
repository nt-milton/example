from django.db import models

from blueprint.choices import ControlBlueprintStatus, SuggestedOwner
from blueprint.models import (
    ActionItemBlueprint,
    ControlFamilyBlueprint,
    ControlGroupBlueprint,
    ImplementationGuideBlueprint,
    TagBlueprint,
)
from certification.models import CertificationSection


class ControlBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Controls Blueprint'

    # Required Fields
    reference_id = models.CharField(unique=True, max_length=100)
    household = models.CharField(null=True, blank=True, max_length=100)
    name = models.TextField(max_length=1024)
    airtable_record_id = models.CharField(blank=True, max_length=512)

    # This field is required in the logic to create controls
    framework_tag = models.CharField(blank=True, max_length=512)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()
    display_id = models.IntegerField(
        default=9999999, verbose_name='display id (within group)'
    )

    # Blank Fields
    description = models.TextField(blank=True)
    suggested_owner = models.CharField(
        max_length=50,
        null=True,
        choices=SuggestedOwner.choices,
    )

    # Default Fields
    status = models.CharField(
        max_length=255,
        choices=ControlBlueprintStatus.choices,
        default=ControlBlueprintStatus.NOT_IMPLEMENTED,
    )

    # Required ForeignKeys
    family = models.ForeignKey(
        ControlFamilyBlueprint,
        related_name='controls',
        null=True,
        on_delete=models.SET_NULL,
    )

    # Non-required ForeignKeys
    group = models.ForeignKey(
        ControlGroupBlueprint,
        null=True,
        blank=True,
        related_name='controls',
        on_delete=models.SET_NULL,
    )
    implementation_guide = models.ForeignKey(
        ImplementationGuideBlueprint,
        null=True,
        blank=True,
        related_name='control',
        on_delete=models.SET_NULL,
    )

    # ManyToMany Fields
    tags = models.ManyToManyField(
        TagBlueprint, related_name='controls', through='ControlBlueprintTag'
    )
    certification_sections = models.ManyToManyField(
        CertificationSection,
        related_name='controls_blueprint',
        through='ControlCertificationSectionBlueprint',
    )
    action_items = models.ManyToManyField(
        ActionItemBlueprint, related_name='controls_blueprint'
    )

    def __str__(self):
        return self.name


# Keep here to avoid circular dependencies
class ControlBlueprintTag(models.Model):
    tag = models.ForeignKey(TagBlueprint, on_delete=models.CASCADE)
    control = models.ForeignKey(
        ControlBlueprint, on_delete=models.CASCADE, related_name='control_tags'
    )

    def __str__(self):
        return str(self.tag)


# Keep here to avoid circular dependencies
class ControlCertificationSectionBlueprint(models.Model):
    certification_section = models.ForeignKey(
        CertificationSection, on_delete=models.CASCADE
    )

    control = models.ForeignKey(
        ControlBlueprint,
        on_delete=models.CASCADE,
    )
