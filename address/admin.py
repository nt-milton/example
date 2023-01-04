from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Address


class AddressAdmin(VersionAdmin):
    list_display = (
        'street1',
        'street2',
        'city',
        'state',
        'zip_code',
        'country',
    )


admin.site.register(Address, AddressAdmin)
