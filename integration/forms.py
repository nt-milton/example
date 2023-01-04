from django import forms

from integration.models import IntegrationVersion
from vendor.models import Vendor


class IntegrationAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(IntegrationAdminForm, self).__init__(*args, **kwargs)
        self.fields['vendor'].queryset = Vendor.objects.order_by('name')


class ConnectionAccountAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ConnectionAccountAdminForm, self).__init__(*args, **kwargs)
        if self.instance.integration_id is not None:
            integration_versions = IntegrationVersion.objects.filter(
                integration__vendor=self.instance.integration.vendor
            )
        else:
            integration_versions = IntegrationVersion.objects.all()
        self.fields['integration_version'].queryset = integration_versions
