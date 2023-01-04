from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    ANCHOR,
    ANCHOR_END,
    ATTACHMENT,
    BLUEPRINT_FORMULA,
    CHIP_DIV_END,
    CHIP_DIV_START,
    DESCRIPTION,
    EVIDENCE_METADATA_AIRTABLE_NAME,
    EVIDENCE_METADATA_REQUIRED_FIELDS,
    NAME,
    REFERENCE_ID,
)
from blueprint.helpers import get_attachment
from blueprint.models.evidence_metadata import EvidenceMetadataBlueprint


@admin.register(EvidenceMetadataBlueprint)
class EvidenceMetadataBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.EVIDENCES_METADATA)
    airtable_tab_name = EVIDENCE_METADATA_AIRTABLE_NAME
    blueprint_required_fields = EVIDENCE_METADATA_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA
    blueprint_model = EvidenceMetadataBlueprint
    model_parameter_name = 'reference_id'
    blueprint_parameter_name_value = REFERENCE_ID

    ordering = ('reference_id',)

    def formatted_reference_id(self, obj):
        url = f'/admin/blueprint/evidencemetadatablueprint/{obj.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.reference_id
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_reference_id.short_description = 'Reference ID'  # type: ignore
    formatted_reference_id.admin_order_field = 'reference_id'  # type: ignore

    def formatted_name(self, obj):
        return format_html('<div style="min-width: 250px;">' + obj.name + CHIP_DIV_END)

    formatted_name.short_description = 'Name'  # type: ignore
    formatted_name.admin_order_field = 'name'  # type: ignore

    official_fields = (
        'formatted_reference_id',
        'formatted_name',
        'description',
        'attachment',
        'airtable_record_id',
        'created_at',
        'updated_at',
    )

    list_display = official_fields
    fields = official_fields

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'name': fields.get(NAME) or '',
            'description': fields.get(DESCRIPTION) or '',
        }

    def execute_after_update_or_create(self, fields: dict, evidence_metadata):
        evidence_metadata.attachment = get_attachment(fields.get(ATTACHMENT) or [])
        evidence_metadata.save()
        return True
