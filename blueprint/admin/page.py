from multiprocessing.pool import ThreadPool

from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.core.handlers.asgi import ASGIRequest
from django.forms import BaseModelForm
from django.http import HttpResponseRedirect
from django.urls import path
from django.views.decorators.http import require_GET

from blueprint.admin import (
    ChecklistBlueprintAdmin,
    ImplementationGuideBlueprintAdmin,
    ObjectAttributeBlueprintAdmin,
    ObjectBlueprintAdmin,
    OfficerBlueprintAdmin,
    QuestionBlueprintAdmin,
    TeamBlueprintAdmin,
    TrainingBlueprintAdmin,
)
from blueprint.admin.action_item import ActionItemBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.admin.control import ControlBlueprintAdmin
from blueprint.admin.control_family import ControlFamilyBlueprintAdmin
from blueprint.admin.control_group import ControlGroupBlueprintAdmin
from blueprint.admin.evidence_metadata import EvidenceMetadataBlueprintAdmin
from blueprint.admin.framework import (
    get_airtable_sync_class as get_airtable_sync_class_certifications,
)
from blueprint.admin.framework import init_update as init_update_certifications
from blueprint.admin.tag import TagBlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import RESPONSE_REDIRECT_PATH
from blueprint.models import (
    ActionItemBlueprint,
    ControlBlueprint,
    ControlFamilyBlueprint,
    ControlGroupBlueprint,
    EvidenceMetadataBlueprint,
    ImplementationGuideBlueprint,
    TagBlueprint,
)
from blueprint.models.checklist import ChecklistBlueprint
from blueprint.models.object import ObjectBlueprint
from blueprint.models.object_attribute import ObjectAttributeBlueprint
from blueprint.models.officer import OfficerBlueprint
from blueprint.models.page import Page
from blueprint.models.question import QuestionBlueprint
from blueprint.models.team import TeamBlueprint
from blueprint.models.training import TrainingBlueprint

pool = ThreadPool()


@admin.register(Page)
class BlueprintPageAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'synched_at',
        'created_by',
        'created_at',
        'updated_at',
    )

    readonly_fields = ['synched_at', 'status_detail']

    change_list_template = "admin/blueprint_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync_all_from_airtable/', sync_all_from_airtable),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        return super(BlueprintPageAdmin, self).changelist_view(
            request, prepare_extra_context(extra_context)
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super(BlueprintPageAdmin, self).get_form(request, obj=obj, **kwargs)

        return prepare_form(obj, form, request)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        update_or_create_secondary_blueprints(obj)


@require_GET
def sync_all_from_airtable(request: ASGIRequest):
    messages.info(request, 'Sync is running in the background')
    pool.apply_async(init_update_all_blueprints, args=(request,))

    return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)


def init_update_for_any_blueprint(request, admin_page: BlueprintAdmin):
    airtable, _ = admin_page.get_airtable_for_blueprint(request)
    if airtable:
        admin_page.init_update(airtable)


def init_update_all_blueprints(request: ASGIRequest):
    #  Never delete certifications
    init_update_certifications(get_airtable_sync_class_certifications(request))

    admin_site = AdminSite()
    init_update_for_any_blueprint(
        request,
        ImplementationGuideBlueprintAdmin(
            model=ImplementationGuideBlueprint, admin_site=admin_site
        ),
    )
    init_update_for_any_blueprint(
        request, QuestionBlueprintAdmin(model=QuestionBlueprint, admin_site=admin_site)
    )
    init_update_for_any_blueprint(
        request, TrainingBlueprintAdmin(model=TrainingBlueprint, admin_site=admin_site)
    )
    init_update_for_any_blueprint(
        request, TeamBlueprintAdmin(model=TeamBlueprint, admin_site=admin_site)
    )
    init_update_for_any_blueprint(
        request,
        ChecklistBlueprintAdmin(model=ChecklistBlueprint, admin_site=admin_site),
    )
    init_update_for_any_blueprint(
        request, ObjectBlueprintAdmin(model=ObjectBlueprint, admin_site=admin_site)
    )
    init_update_for_any_blueprint(
        request,
        ObjectAttributeBlueprintAdmin(
            model=ObjectAttributeBlueprint, admin_site=admin_site
        ),
    )

    init_update_for_any_blueprint(
        request, OfficerBlueprintAdmin(model=OfficerBlueprint, admin_site=admin_site)
    )

    init_update_for_any_blueprint(
        request, TagBlueprintAdmin(model=TagBlueprint, admin_site=admin_site)
    )
    init_update_for_any_blueprint(
        request,
        ControlGroupBlueprintAdmin(model=ControlGroupBlueprint, admin_site=admin_site),
    )
    init_update_for_any_blueprint(
        request,
        ControlFamilyBlueprintAdmin(
            model=ControlFamilyBlueprint, admin_site=admin_site
        ),
    )
    init_update_for_any_blueprint(
        request, ControlBlueprintAdmin(model=ControlBlueprint, admin_site=admin_site)
    )
    init_update_for_any_blueprint(
        request,
        ActionItemBlueprintAdmin(model=ActionItemBlueprint, admin_site=admin_site),
    )
    init_update_for_any_blueprint(
        request,
        EvidenceMetadataBlueprintAdmin(
            model=EvidenceMetadataBlueprint, admin_site=admin_site
        ),
    )


def prepare_form(obj: Page, form: BaseModelForm, request: ASGIRequest) -> BaseModelForm:
    return deactivate_form_fields_by_default(
        deactivate_fields_for_secondary_blueprints(
            obj=obj,
            form=set_default_values_and_deactivate_when_global_exists(
                obj=obj,
                form=set_form_default_user(obj, set_form_default_page(form), request),
            ),
        )
    )


def set_form_default_user(
    obj: Page, form: BaseModelForm, request: ASGIRequest
) -> BaseModelForm:
    if not obj:
        form.base_fields['created_by'].initial = request.user
    return form


def set_form_default_page(form: BaseModelForm) -> BaseModelForm:
    form.base_fields['name'].initial = BlueprintPage.GLOBAL
    return form


def set_default_values_and_deactivate_when_global_exists(
    obj: Page, form: BaseModelForm
) -> BaseModelForm:
    global_blueprint = Page.objects.filter(name=BlueprintPage.GLOBAL).first()

    if not obj and global_blueprint:
        set_default_values(form, global_blueprint)
        deactivate_form_fields(form)
    return form


def deactivate_fields_for_secondary_blueprints(
    obj: Page, form: BaseModelForm
) -> BaseModelForm:
    if obj and obj.name != BlueprintPage.GLOBAL:
        deactivate_form_fields(form)
    return form


def deactivate_form_fields_by_default(form: BaseModelForm) -> BaseModelForm:
    form.base_fields['created_by'].disabled = True
    return form


def deactivate_form_fields(form: BaseModelForm):
    form.base_fields['airtable_link'].disabled = True
    form.base_fields['airtable_api_key'].disabled = True


def set_default_values(form: BaseModelForm, blueprint: Page):
    form.base_fields['airtable_link'].initial = blueprint.airtable_link
    form.base_fields['airtable_api_key'].initial = blueprint.airtable_api_key


def update_or_create_secondary_blueprints(obj: Page):
    for name in BlueprintPage.values:
        if name == BlueprintPage.GLOBAL:
            continue
        create_blueprint_record(obj, name)


def create_blueprint_record(obj: Page, name: str):
    Page.objects.update_or_create(
        name=name,
        defaults={
            'airtable_link': obj.airtable_link,
            'airtable_api_key': obj.airtable_api_key,
            'created_by': obj.created_by,
        },
    )


def prepare_extra_context(extra_context) -> dict:
    extra_context = extra_context or {}
    exists = Page.objects.filter(name=BlueprintPage.GLOBAL).exists()

    extra_context['show_add_button'] = not exists
    extra_context['show_update_button'] = exists
    return extra_context
