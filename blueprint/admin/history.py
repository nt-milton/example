from django.contrib import admin

from blueprint.models.history import BlueprintHistory


@admin.register(BlueprintHistory)
class BlueprintHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'organization',
        'created_by',
        'upload_action',
        'content_description',
        'status',
        'created_at',
        'updated_at',
    )
