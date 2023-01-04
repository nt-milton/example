from django.contrib import admin
from reversion.admin import VersionAdmin

from vendor.models import (
    Category,
    OrganizationVendor,
    OrganizationVendorEvidence,
    OrganizationVendorStakeholder,
    Vendor,
    VendorCandidate,
    VendorCertification,
)


class VendorCertificationAdmin(admin.TabularInline):
    model = VendorCertification


class VendorAdmin(VersionAdmin):
    list_display = ('id', 'name', 'website', 'description', 'is_public')
    list_filter = ('categories', 'certifications', 'is_public')
    search_fields = ['name', 'website']
    ordering = ('id',)
    inlines = [
        VendorCertificationAdmin,
    ]


admin.site.register(Vendor, VendorAdmin)


class OrganizationVendorStakeholderAdmin(admin.TabularInline):
    model = OrganizationVendorStakeholder


class OrganizationVendorEvidenceAdmin(admin.TabularInline):
    model = OrganizationVendorEvidence


class OrganizationVendorAdmin(VersionAdmin):
    list_display = (
        'vendor',
        'organization',
        'status',
        'financial_exposure',
        'operational_exposure',
        'risk_rating',
    )
    list_filter = ('status', 'organization')
    inlines = [
        OrganizationVendorStakeholderAdmin,
        OrganizationVendorEvidenceAdmin,
    ]


admin.site.register(OrganizationVendor, OrganizationVendorAdmin)


class CategoryAdmin(VersionAdmin):
    list_display = ('id', 'name')
    ordering = ('id',)


admin.site.register(Category, CategoryAdmin)


class VendorCandidateAdmin(VersionAdmin):
    autocomplete_fields = ('organization', 'vendor')
    search_fields = ('name', 'organization__name', 'vendor__name')
    list_display = ('id', 'name', 'status', 'organization', 'vendor')
    ordering = ('id', 'organization')
    list_filter = ('status', 'organization')


admin.site.register(VendorCandidate, VendorCandidateAdmin)
