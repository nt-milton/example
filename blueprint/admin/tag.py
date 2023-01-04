from django.contrib import admin

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import TAG_REQUIRED_FIELDS, TAGS_AIRTABLE_NAME
from blueprint.models import TagBlueprint


@admin.register(TagBlueprint)
class TagBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.TAGS)
    airtable_tab_name = TAGS_AIRTABLE_NAME
    blueprint_required_fields = TAG_REQUIRED_FIELDS

    blueprint_model = TagBlueprint
    model_parameter_name = 'name'
    blueprint_parameter_name_value = 'Name'

    list_display = (
        'name',
        'airtable_record_id',
        'created_at',
        'updated_at',
    )

    search_fields = ('name',)
