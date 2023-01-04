from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from reversion.admin import VersionAdmin

from .metadata import Metadata
from .models import Attribute, LaikaObject, LaikaObjectType
from .types import AttributeTypeFactory

INSTANCE = 'instance'
INITIAL = 'initial'
IS_PROTECTED = 'is_protected'
DEFAULT_VALUE = 'default_value'
SELECT_OPTIONS = 'select_options'


class AttributeForm(forms.ModelForm):
    default_value = forms.CharField(required=False)
    select_options = forms.CharField(required=False)
    is_protected = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        if INSTANCE in kwargs:
            attribute = kwargs[INSTANCE]
            metadata = Metadata(attribute._metadata)

            if INITIAL not in kwargs:
                kwargs[INITIAL] = {}
            kwargs[INITIAL].update(metadata.to_json(csv_select_options=True))

        super(AttributeForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super(AttributeForm, self).save(commit=False)
        metadata = Metadata()

        if SELECT_OPTIONS in self.cleaned_data:
            metadata.set_select_options_from_csv(self.cleaned_data[SELECT_OPTIONS])
        if DEFAULT_VALUE in self.cleaned_data:
            attribute_type = AttributeTypeFactory.get_attribute_type(instance)
            metadata.default_value = attribute_type.format(
                self.cleaned_data[DEFAULT_VALUE]
            )
        if IS_PROTECTED in self.cleaned_data:
            metadata.is_protected = self.cleaned_data[IS_PROTECTED]

        instance._metadata = metadata.to_json()

        if commit:
            instance.save()
        return instance

    class Meta:
        model = Attribute
        fields = '__all__'


class LaikaObjectAttributeAdmin(admin.TabularInline):
    model = Attribute
    fields = [
        'name',
        'sort_index',
        'attribute_type',
        'min_width',
        'default_value',
        'select_options',
        'is_protected',
        'is_manually_editable',
    ]

    form = AttributeForm


class LaikaObjectAdmin(VersionAdmin):
    model = LaikaObject
    list_display = ('id', 'object_type', 'created_at', 'updated_at', 'data')
    list_per_page = 10
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ['object_type']


class LaikaObjectTypeForm(forms.ModelForm):
    class Meta:
        model = LaikaObjectType
        fields = '__all__'

    def clean_type_name(self):
        type_name = self.cleaned_data['type_name']
        if 'default' == type_name:
            raise ValidationError('Type name cannot be "default"')
        return type_name


class LaikaObjectTypeAdmin(VersionAdmin):
    model = LaikaObjectType
    list_display = (
        'organization',
        'display_name',
        'display_index',
        'type_name',
        'icon_name',
        'color',
        'is_system_type',
    )
    fields = [
        'organization',
        ('display_name', 'is_system_type'),
        'display_index',
        'type_name',
        'icon_name',
        'color',
        'description',
    ]
    list_filter = ('organization', 'display_name', 'is_system_type')
    inlines = [LaikaObjectAttributeAdmin]

    form = LaikaObjectTypeForm


admin.site.register(LaikaObjectType, LaikaObjectTypeAdmin)
admin.site.register(LaikaObject, LaikaObjectAdmin)
